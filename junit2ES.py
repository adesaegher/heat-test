#!/usr/bin/env python
#connect to our cluster
from elasticsearch import Elasticsearch
es = Elasticsearch([{'host': '10.0.0.61', 'port': 9200}])
from datetime import datetime
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
import xml.etree.ElementTree as ElementTree
from itertools import groupby
import os
import json

def send_to_elk(testjson):
    es.index(index='rally', doc_type='tests-result', body={"": json.loads(testjson), "timestamp": datetime.now()})

def find_test_data(junit_xml_filename):
    """
    flatten all the data from junit based xml file into a list of dicts

    :param junit_xml_filename: the output from py.test --junit-xml
    :return:
    """

    tests_list = []

    xml_test = open(junit_xml_filename, 'r').read()

    et = ElementTree.fromstring(xml_test)
    for test in et.iter('testcase'):

        item = dict(**test.attrib)
        outcome = None
        failure = test.find("failure")
        error = test.find("error")
        skipped = test.find("skipped")

        if failure is not None:
            item['failure_message'] = failure.attrib['message']
            outcome = 'failure'
        elif skipped is not None:
            item['skip_message'] = skipped.attrib['message']
            outcome = 'skipped'
        elif error is not None:
            item['error_message'] = error.attrib['message']
            outcome = 'error'
        else:
            outcome = 'success'

        item['outcome'] = outcome
        item['run_time'] = item['time']
        # time is a built in in Logstash
        del item['time']

        tests_list.append(item)

        # filter by group, and merge result
    cumulative_keys = ['outcome', 'run_time']
    tests_list_grouped = []
    for key, group in groupby(tests_list, lambda x: (x['name'], x['classname'])):
        item = dict()
        for thing in group:
            # merge needed values
            if item.has_key('outcome'):
                item['outcome'] += " & " + thing['outcome']

            if item.has_key('run_time'):
                item['run_time'] += thing['run_time']

                # overwrite the rest
            for key in thing.keys():
                if key not in cumulative_keys or not item.has_key(key):
                    item[key] = thing[key]
        tests_list_grouped.append(item)

    return tests_list_grouped

def execute():

    junit_file = '/home/ec2-user/output.xml'
    log_dir = os.environ.get('LOG_DEST_DIR', './')

    if junit_file:  # if found xml file, send all of it
        tests_list = find_test_data(junit_file)
        for i, test in enumerate(tests_list):

            # save data to a file
            with open(os.path.join(log_dir, 'job_info%d.json' % i), 'w+') as f:
                f.write(json.dumps(test, sort_keys=True,
                                   indent=4, separators=(',', ': ')))
            testjson = json.dumps(test, sort_keys=True,
                               indent=4, separators=(',', ': '))
            send_to_elk(testjson)
execute()
