#!/usr/bin/env python3
import argparse, re, requests
import glob, os
from datetime import datetime

def main(domain, cookie):
    if domain == 'cn':
        is_intl = False
        print('dumping LeetCode China ...')
    else:
        is_intl = True
        print('dumping LeetCode International ...')

    if is_intl:
        # For LeetCode International
        base_url = 'https://leetcode.com'
    else:
        # For LeetCode China
        base_url = 'https://leetcode.cn'
    
    if cookie == None:
        print ('You must set cookie by adding option \'-c\' before running this script!')
        return
        # if is_intl:
            # cookie = '<your leetcode.com cookie here>'
        # else:
            # cookie = '<your leetcode.cn cookie here>'

    if is_intl:
        dump_folder_name = 'Dump/'
    else:
        dump_folder_name = 'DumpCN/'

    if not os.path.exists(dump_folder_name):
        os.mkdir(dump_folder_name)

    session = requests.Session()

    headers = {
        'referer': base_url,
        'x-requested-with': 'XMLHttpRequest',
        'cookie': cookie
    }

    # GraphQL Endpoint
    graphql_url = base_url + '/graphql/'
    
    # GraphQL - get problem list
    query = {
        "operationName": "allQuestions",
        "variables": {},
        "query": "query allQuestions {\n  allQuestions {\n    ...questionSummaryFields\n    __typename\n  }\n}\n\nfragment questionSummaryFields on QuestionNode {\n  title\n  titleSlug\n  translatedTitle\n  questionId\n  questionFrontendId\n  status\n  difficulty\n  isPaidOnly\n  __typename\n}\n"
    }

    response = session.request('POST', graphql_url, headers = headers, json = query)
    if response.status_code == 200:
        print('fetch problem list - ok')
    else:
        print('fetch problem list - fail')
        print(response.status_code)
        print(response.text)
        return
    problems = response.json()['data']['allQuestions']

    front_end_problem_map = {}
    for problem in problems:
        front_end_problem_map[problem['questionFrontendId']] = problem

    input_problem_id = input('input problem ids to download(0 means all, use whitespace to split multiple problem ids): ')
    if input_problem_id == '0':
        ids = [problems[n]['questionFrontendId'] for n in range(len(problems)) if problems[n]['status'] == 'ac']
    elif input_problem_id:
        ids = [n for n in input_problem_id.split()]

    dumped = 0
    skipped = 0
    timestamp_start = datetime.utcnow()
    warning_message_map = {}
    for id in ids:
        if id not in front_end_problem_map:
            skipped += 1
            continue
        problem = front_end_problem_map[id]

        filename_woext = dump_folder_name + id + '.' + problem['titleSlug'] + '.*'
        if file_exists(filename_woext):
            print('code for #%s exists - skipping' % id)
            skipped += 1
            continue

        print('downloading #%s %s' % (id, problem['title']))

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

        response = session.request('POST', graphql_url, headers = headers, json = query)
        if response.status_code == 200:
            print('fetch submission list for #%s - ok' % id)
        else:
            print('fetch submission list for #%s - fail' % id)
            print(response.status_code)
            print(response.text)
            continue
        
        submissions = response.json()['data']['submissionList']['submissions']

        latest_accepted = {}
        extension = {
                'c': 'c',
                'cpp': 'cpp',
                'csharp': 'cs',
                'java': 'java',
                'javascript': 'js',
                'python': 'py',
                'python3': 'py',
                'golang': 'go',
                'mysql': 'sql',
                # Add more lang
        }
        for input_problem_id in submissions:
            if input_problem_id['statusDisplay'] == 'Accepted' and input_problem_id['lang'] not in latest_accepted:
                latest_accepted[input_problem_id['lang']] = input_problem_id

        # get ac code
        find_ac = False
        if is_intl:
            # International
            for submission in latest_accepted.values():
                url = base_url + submission['url']

                response = session.request('GET', url, headers = headers)
                if response.status_code != 200:
                    print('fetch submission detail for #%s - submission #%s - ok' % (id, submission['id']))
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

                if submission['lang'] not in extension:
                    warning_message_map[id] = 'Code extension not found, please manually add the extension name into the script, lang code [%s].' % submission['lang']
                    continue
                filename = dump_folder_name + id + '.' + problem['titleSlug'] + '.' + extension[submission['lang']]
                find_ac = True
        else:
            # China
            # get submission detail
            for submission in latest_accepted.values():
                query = {
                    "operationName": "mySubmissionDetail",
                    "variables": {
                        "id": submission['id']
                    },
                    "query": "query mySubmissionDetail($id: ID!) {\n  submissionDetail(submissionId: $id) {\n    id\n    code\n    runtime\n    memory\n    rawMemory\n    statusDisplay\n    timestamp\n    lang\n    isMine\n    passedTestCaseCnt\n    totalTestCaseCnt\n    sourceUrl\n    question {\n      titleSlug\n      title\n      translatedTitle\n      questionId\n      __typename\n    }\n    ... on GeneralSubmissionNode {\n      outputDetail {\n        codeOutput\n        expectedOutput\n        input\n        compileError\n        runtimeError\n        lastTestcase\n        __typename\n      }\n      __typename\n    }\n    submissionComment {\n      comment\n      flagType\n      __typename\n    }\n    __typename\n  }\n}\n"
                }

                response = session.request('POST', graphql_url, headers = headers, json = query)
                if response.status_code == 200:
                    print('fetch submission detail for #%s - submission #%s - ok' % (id, submission['id']))
                else:
                    print('fetch submission detail for #%s - submission #%s - fail' % (id, submission['id']))
                    print(response.status_code)
                    print(response.text)
                    continue

                code = response.json()['data']['submissionDetail']['code']

                if submission['lang'] not in extension:
                    warning_message_map[id] = 'Code extension not found, please manually add the extension name into the script, lang code [%s].' % submission['lang']
                    continue
                filename = dump_folder_name + id + '.' + problem['titleSlug'] + '.' + extension[submission['lang']]
                find_ac = True

        # write to file
        if find_ac:
            with open(filename, mode='w', encoding='utf-8') as fp:
                fp.write(code)
            print('wrote to ' + filename)
            dumped += 1
        else:
            print('no accpted code for question #%s.' % id)
            skipped += 1

    print('Warning Messages')
    for id, message in warning_message_map.items():
        print('\tQuestion #%s - %s' % (id, message))
    print()
    print('Finished')
    print('Requested Questions - ' + str(len(ids)))
    print('Dumped - %d' % dumped)
    print('Skipped - %d' % skipped)
    print('Failed - %d' % (len(ids) - dumped - skipped))
    total_minutes = int(round((datetime.utcnow() - timestamp_start).total_seconds() / 60))
    total_seconds = int(round((datetime.utcnow() - timestamp_start).total_seconds() % 60))
    print('Total Time - %s min %s sec' % (total_minutes, total_seconds))    

def file_exists(filepath):
    for filepath_object in glob.glob(filepath):
        if os.path.isfile(filepath_object):
            return True
    return False

parser = argparse.ArgumentParser()
parser.add_argument('--domain', '-d', help='intl (by default) for International or cn for China', default='intl')
parser.add_argument('--cookie', '-c', help='cookie of the leetcode endpoint')
args = parser.parse_args()

if __name__ == '__main__':
    main(args.domain, args.cookie)
