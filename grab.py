#!/usr/bin/env python3
from datetime import datetime
import argparse, re, requests
import glob, os
import threading
import traceback

# Third-party Packages
import chevron

class ProblemListThread(threading.Thread):
    def __init__(self, index, problem_per_request, sema):
        threading.Thread.__init__(self)
        self.index = index
        self.problem_per_request = problem_per_request
        self.sema = sema
    def run(self):
        self.sema.acquire()
        fetch_question_list(self.index, self.problem_per_request)
        self.sema.release()

class ProblemThread(threading.Thread):
    def __init__(self, problem_map, problem_id, sema):
        threading.Thread.__init__(self)
        self.problem_map = problem_map
        self.problem_id = problem_id
        self.sema = sema
    def run(self):
        self.sema.acquire()
        fetch_question(self.problem_map, self.problem_id)
        self.sema.release()

class AtomicInteger():
    def __init__(self, value=0):
        self._value = int(value)
        self._lock = threading.Lock()
        
    def inc(self, d=1):
        with self._lock:
            self._value += int(d)
            return self._value

    def dec(self, d=1):
        return self.inc(-d)    

    @property
    def value(self):
        with self._lock:
            return self._value

    @value.setter
    def value(self, v):
        with self._lock:
            self._value = int(v)
            return self._value

is_intl = True
base_url = 'https://leetcode.com'
graphql_url = base_url + '/graphql/'
dump_folder_path = './dump/'
headers = {}

# runtime stats - atomic
requested_submissions = AtomicInteger(0)
dumped_questions = AtomicInteger(0)
dumped_submissions = AtomicInteger(0)
skipped_questions = AtomicInteger(0)
skipped_submissions = AtomicInteger(0)
problem_id_to_warning_message = {}
problem_id_to_accepted_languages_set = {}
front_end_problem_map = {}

# Add new languages here
language_map = {
    'c': { 'ext': 'c', 'display': 'C' },
    'cpp': { 'ext': 'cpp', 'display': 'C++' },
    'csharp': { 'ext': 'cs', 'display': 'C#' },
    'java': { 'ext': 'java', 'display': 'Java' },
    'javascript': { 'ext': 'js', 'display': 'JavaScript' },
    'python': { 'ext': 'py', 'display': 'Python' },
    'python3': { 'ext': 'py', 'display': 'Python3' },
    'golang': { 'ext': 'go', 'display': 'Go' },
    'mysql': { 'ext': 'sql', 'display': 'MySQL' },
}

def main(domain, cookie, threads):
    global is_intl
    global base_url
    global graphql_url
    global dump_folder_path
    global headers
    global problem_id_to_accepted_languages_set
    global front_end_problem_map

    timestamp_start = datetime.utcnow()

    sema = threading.Semaphore(value=int(threads))

    if domain == 'cn':
        # LeetCode International
        is_intl = False
        base_url = 'https://leetcode.cn'
        print('dumping LeetCode China ...')
    else:
        # LeetCode China
        is_intl = True
        base_url = 'https://leetcode.com'
        print('dumping LeetCode International ...')
    
    if cookie == None:
        print ('You must set cookie by adding option \'-c\' before running this script!')
        return

    if is_intl:
        dump_folder_path = './dump/'
    else:
        dump_folder_path = './dump-cn/'

    if not os.path.exists(dump_folder_path):
        os.mkdir(dump_folder_path)

    headers = {
        'referer': base_url,
        'x-requested-with': 'XMLHttpRequest',
        'cookie': cookie
    }

    # GraphQL Endpoint
    graphql_url = base_url + '/graphql/'
    
    # get number of questions
    all_question_url = base_url + '/api/problems/all/'
    with requests.Session() as s:
        response = s.request('GET', all_question_url, headers = headers)
    if response.status_code != 200:
        print(response.status_code)
        print(response.text)
        return
    all_question_number = response.json()['num_total']

    # GraphQL - get problem list recursively
    threads = []
    index = 0
    problem_per_request = 100
    while True:
        thread = ProblemListThread(index=index, problem_per_request=problem_per_request, sema=sema)
        thread.start()
        threads.append(thread)
        index += problem_per_request
        if index >= all_question_number:
            break
    for t in threads:
        t.join()
    
    front_end_problem_map = dict(sorted(front_end_problem_map.items(), key= lambda x:x[1]['id']))
    problem_id_to_accepted_languages_set = {k: set() for k in front_end_problem_map.keys()}

    input_problem_id = input('input problem ids to download(0 means all, use whitespace to split multiple problem ids): ')
    if input_problem_id == '0':
        ids = [k for k, v in front_end_problem_map.items() if v['status'] != None and v['status'].lower() == 'ac']
    elif input_problem_id:
        ids = [n for n in input_problem_id.split() if n in front_end_problem_map and front_end_problem_map[n]['status'] != None and front_end_problem_map[n]['status'].lower() == 'ac']

    threads = []
    for id in ids:
        thread = ProblemThread(problem_map=front_end_problem_map, problem_id=id, sema=sema)
        thread.start()
        threads.append(thread)
    for t in threads:
        t.join()

    # write to readme
    accepted_problems = [v for v in front_end_problem_map.values() if v['status'] != None and v['status'].lower() == 'ac']
    language_set_all = set()
    for language_set in problem_id_to_accepted_languages_set.values():
        language_set = sorted(language_set)
        language_set_all = language_set_all.union(language_set)
    language_set_all = sorted(language_set_all)
    total_num = len(front_end_problem_map)
    locked_num =len([v for v in front_end_problem_map.values() if v['paidOnly']])
    solved_num = len(accepted_problems)
    hard_num = len([v for v in accepted_problems if v['difficulty'].lower() == 'hard'])
    medium_num = len([v for v in accepted_problems if v['difficulty'].lower() == 'medium'])
    easy_num = len([v for v in accepted_problems if v['difficulty'].lower() == 'easy'])
    
    solutions = [{
        'id': v['frontendQuestionId'],
        'domain': 'com' if is_intl else 'cn',
        'title': v['titleSlug'],
        'solutionLinks': str.join(' ', [('[%s](%s%s.%s.%s)' % (language_map[language]['display'], dump_folder_path, v['frontendQuestionId'], v['titleSlug'], language_map[language]['ext'])).replace(' ', '-') for language in problem_id_to_accepted_languages_set[v['frontendQuestionId']]]),
        'difficulty': v['difficulty'],
        'paidOnly': ':heavy_check_mark:' if v['paidOnly'] else '',
        'acceptance': '{:.2%}'.format(v['acRate'] / 100 if is_intl else v['acRate']),
        'tags': str.join(' \| ', [tag['name'] for tag in v['topicTags']])
    } for v in accepted_problems] 

    language = str.join(', ', [language_map[language]['display'] for language in language_set_all])
    data = {
        'language': language,
        'time': datetime.now().date(),
        'total': total_num,
        'locked': locked_num,
        'solved': solved_num,
        'hard': hard_num,
        'medium': medium_num,
        'easy': easy_num,
        'solutions': solutions,
    }

    generate(path='./', data=data)

    print('Warning Messages')
    for id, message in problem_id_to_warning_message.items():
        print('\tQuestion #%s - %s' % (id, message))
    print()
    print('Finished')
    print('Requested Questions - %d' % len(ids))
    print('\tDumped - %d' % dumped_questions.value)
    print('\tSkipped - %d' % skipped_questions.value)
    print('\tFailed - %d' % (len(ids) - dumped_questions.value - skipped_questions.value))
    print('Requested Submissions %d ' % requested_submissions.value)
    print('\tDumped - %d' % dumped_submissions.value)
    print('\tSkipped - %d' % skipped_submissions.value)
    print('\tFailed - %d' % (requested_submissions.value - dumped_submissions.value - skipped_submissions.value))
    timestamp_end = datetime.utcnow()
    total_minutes = int(round((timestamp_end - timestamp_start).total_seconds() / 60))
    total_seconds = int(round((timestamp_end - timestamp_start).total_seconds() % 60))
    print('Total Time - %s min %s sec' % (total_minutes, total_seconds))    

def fetch_question_list(index, problem_per_request):
    query_str = 'query problemsetQuestionList($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {\n  problemsetQuestionList: questionList(\n    categorySlug: $categorySlug\n    limit: $limit\n    skip: $skip\n    filters: $filters\n  ) {\n    total: totalNum\n    questions: data {\n      acRate\n      difficulty\n      freqBar\n      frontendQuestionId: questionFrontendId\n      isFavor\n      paidOnly: isPaidOnly\n      status\n      title\n      titleSlug\n      topicTags {\n        name\n        id\n        slug\n      }\n      hasSolution\n      hasVideoSolution\n    }\n  }\n}\n    ' if is_intl else 'query problemsetQuestionList($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {\n  problemsetQuestionList(\n    categorySlug: $categorySlug\n    limit: $limit\n    skip: $skip\n    filters: $filters\n  ) {\n    hasMore\n    total\n    questions {\n      acRate\n      difficulty\n      freqBar\n      frontendQuestionId\n      isFavor\n      paidOnly\n      solutionNum\n      status\n      title\n      titleCn\n      titleSlug\n      topicTags {\n        name\n        nameTranslated\n        id\n        slug\n      }\n      extra {\n        hasVideoSolution\n        topCompanyTags {\n          imgUrl\n          slug\n          numSubscribed\n        }\n      }\n    }\n  }\n}\n    '
    query = {
        "operationName": "problemsetQuestionList",
        "variables": {
            "categorySlug": "",
            "skip": index,
            "limit": problem_per_request,
            "filters": {},
        },
        "query": query_str,
    }

    with requests.Session() as s:
        response = s.request('POST', graphql_url, headers = headers, json = query)
    if response.status_code == 200:
        print('fetch problem list %d - %d - ok' % (index + 1, index + problem_per_request))
    else:
        print('fetch problem list %d - %d - fail' % (index + 1, index + problem_per_request))
        print(response.status_code)
        print(response.text)
        return
    
    problem_delta_list = response.json()['data']['problemsetQuestionList']['questions']
    for idx, problem in enumerate(problem_delta_list):
        problem['id'] = index + idx
    problems_delta_map = { n['frontendQuestionId']: n for n in problem_delta_list}
    front_end_problem_map.update(problems_delta_map)

def fetch_question(problem_map, problem_id):
    dumped_flag = False
    skipped_flag = True

    if problem_id not in problem_map:
        skipped_questions.inc()
        return
    problem = problem_map[problem_id]

    print('downloading #%s %s' % (problem_id, problem['title']))

    # get submission list
    query = {
        "operationName": "Submissions",
        "variables": {
            "offset": 0,
            "limit": 20,
            "lastKey": None,
            "questionSlug": problem['titleSlug']
        },
        "query": "query Submissions($offset: Int!, $limit: Int!, $lastKey: String, $questionSlug: String!) {\n  submissionList(offset: $offset, limit: $limit, lastKey: $lastKey, questionSlug: $questionSlug) {\n    lastKey\n    hasNext\n    submissions {\n      id\n      statusDisplay\n      lang\n      runtime\n      timestamp\n      url\n      isPending\n      memory\n      __typename\n    }\n    __typename\n  }\n}\n"
    }

    with requests.Session() as s:
        response = s.request('POST', graphql_url, headers = headers, json = query)
    if response.status_code == 200:
        print('fetch submission list for #%s - ok' % problem_id)
    else:
        print('fetch submission list for #%s - fail' % problem_id)
        print(response.status_code)
        print(response.text)
        return
    
    submissions = response.json()['data']['submissionList']['submissions']

    try:
        latest_accepted = {}
        for input_problem_id in submissions:
            if input_problem_id['statusDisplay'] == 'Accepted' and input_problem_id['lang'] not in latest_accepted:
                latest_accepted[input_problem_id['lang']] = input_problem_id
                requested_submissions.inc()

        # get ac code
        for submission in latest_accepted.values():        
            # check if language tag is supported
            if submission['lang'] not in language_map:
                problem_id_to_warning_message[problem_id] = 'Code extension not found, please manually add the extension name into the script, lang code [%s].' % submission['lang']
                skipped_submissions.inc()
                continue

            problem_id_to_accepted_languages_set[problem_id].add(submission['lang'])

            # check if file exists
            filename = dump_folder_path + problem_id + '.' + problem['titleSlug'] + '.' + language_map[submission['lang']]['ext']
            if file_exists(filename):
                print('code for #%s exists - skipping' % problem_id)
                skipped_submissions.inc()
                continue

            skipped_flag = False

            # downloading
            if is_intl:
                # International
                submission_url = base_url + submission['url']

                with requests.Session() as s:
                    response = s.request('GET', submission_url, headers = headers)
                if response.status_code != 200:
                    print('fetch submission detail for #%s - submission #%s - ok' % (problem_id, submission['id']))
                    print(response.status_code)
                    print(response.text)
                    continue
                match = re.search('submissionCode: \'(.*)\',', response.text)
                if not match[1]:
                    print('can not parse the submitted code block from raw response.')
                    print(response.text)
                    continue

                print('got %s submission' % (submission['lang']))

                code = match[1].encode('ascii', 'backslashreplace').decode('unicode_escape', 'backslashreplace')
            else:
                # China
                query = {
                    "operationName": "mySubmissionDetail",
                    "variables": {
                        "id": submission['id']
                    },
                    "query": "query mySubmissionDetail($id: ID!) {\n  submissionDetail(submissionId: $id) {\n    id\n    code\n    runtime\n    memory\n    rawMemory\n    statusDisplay\n    timestamp\n    lang\n    isMine\n    passedTestCaseCnt\n    totalTestCaseCnt\n    sourceUrl\n    question {\n      titleSlug\n      title\n      translatedTitle\n      questionId\n      __typename\n    }\n    ... on GeneralSubmissionNode {\n      outputDetail {\n        codeOutput\n        expectedOutput\n        input\n        compileError\n        runtimeError\n        lastTestcase\n        __typename\n      }\n      __typename\n    }\n    submissionComment {\n      comment\n      flagType\n      __typename\n    }\n    __typename\n  }\n}\n"
                }

                with requests.Session() as s:
                    response = s.request('POST', graphql_url, headers = headers, json = query)
                if response.status_code == 200:
                    print('fetch submission detail for #%s - submission #%s - ok' % (problem_id, submission['id']))
                else:
                    print('fetch submission detail for #%s - submission #%s - fail' % (problem_id, submission['id']))
                    print(response.status_code)
                    print(response.text)
                    continue

                res = response.json()
                code = response.json()['data']['submissionDetail']['code']

            # write to file
            write_to_file(filename=filename, content=code)
            dumped_submissions.inc()
            dumped_flag = True
        
        if dumped_flag:
            dumped_questions.inc()
        if skipped_flag:
            skipped_questions.inc()
    except Exception as e:
        traceback.print_exc()
        if res != None:
            print(res)
        problem_id_to_warning_message[problem_id] = e
            
def file_exists(filepath):
    for filepath_object in glob.glob(filepath):
        if os.path.isfile(filepath_object):
            return True
    return False

def write_to_file(filename, content):
    with open(filename, mode='w', encoding='utf-8') as fp:
        fp.write(content)
    print('wrote to ' + filename)

def generate(path, data):
    with open('./README.tql', mode='r', encoding='utf-8') as fp:
        template_content = fp.read()
        print('read markdown template.')
    
    readme_content = chevron.render(template=template_content, data=data)

    if not os.path.exists(path):
        os.mkdir(path)
    write_to_file(path + '/dumped-readme.md', readme_content)

parser = argparse.ArgumentParser()
parser.add_argument('--domain', '-d', help='intl (by default) for International or cn for China', default='intl')
parser.add_argument('--cookie', '-c', help='cookie of the leetcode endpoint')
parser.add_argument('--threads', '-t', help='thread number (8 by default)', default=8)
args = parser.parse_args()

if __name__ == '__main__':
    main(args.domain, args.cookie, args.threads)
