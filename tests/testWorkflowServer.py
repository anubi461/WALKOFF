import unittest
import json
from os import path
import os

from tests.util.assertwrappers import orderless_list_compare, post_with_status_check, get_with_status_check
from tests.config import test_apps_path, test_workflows_path_with_generated
from server import flaskserver as flask_server
from core import helpers
from shutil import copy2

import core.config.paths


class TestWorkflowServer(unittest.TestCase):
    def setUp(self):
        self.app = flask_server.app.test_client(self)
        self.app.testing = True
        self.app.post('/login', data=dict(email='admin', password='admin'), follow_redirects=True)
        response = self.app.post('/key', data=dict(email='admin', password='admin'),
                                 follow_redirects=True).get_data(as_text=True)

        self.key = json.loads(response)["auth_token"]
        self.headers = {"Authentication-Token": self.key}

        core.config.paths.workflows_path = test_workflows_path_with_generated
        core.config.paths.apps_path = test_apps_path
        flask_server.running_context.controller.workflows = {}
        flask_server.running_context.controller.load_all_workflows_from_directory(path=
                                                                                  test_workflows_path_with_generated)
        if ('test.workflow' in os.listdir(core.config.paths.workflows_path)
            and 'test_copy.workflow_bkup' not in os.listdir(core.config.paths.workflows_path)):
            copy2(os.path.join(core.config.paths.workflows_path, 'test.workflow'),
                  os.path.join(core.config.paths.workflows_path, 'test_copy.workflow_bkup'))
        elif 'test_copy.workflow_bkup' in os.listdir(core.config.paths.workflows_path):
            copy2(os.path.join(core.config.paths.workflows_path, 'test_copy.workflow_bkup'),
                  os.path.join(core.config.paths.workflows_path, 'test.workflow'))

        self.empty_workflow_json = \
            {'status': 'success',
             'workflow': {'steps': [],
                          'name': 'test_name',
                          'options': {'children': {},
                                      'enabled': 'True',
                                      'scheduler': {'args': {'interval': '0.1',
                                                             'eDT': '2016-3-15 12:00:00',
                                                             'sDT': '2016-1-1 12:00:00'},
                                                    'autorun': u'false',
                                                    'type': u'cron'}}}}
        self.hello_world_json = \
            {'steps': [{'group': 'nodes',
                        'data': {'id': 'start',
                                 'parameters': {'errors': [{'flags': [], 'name': '1'}],
                                                'name': 'start',
                                                'app': 'HelloWorld',
                                                'next': [{'flags': [{'action': 'regMatch',
                                                                     'args': {
                                                                         'regex': {
                                                                             'key': 'regex',
                                                                             'value': '(.*)',
                                                                             'format': 'str'}},
                                                                     'filters': [{
                                                                         'action': 'length',
                                                                         'args': {}}]}],
                                                          'name': '1'}],
                                                'action': 'repeatBackToMe',
                                                'device': 'hwTest',
                                                'input': {'call': {'key': 'call',
                                                                   'value': 'Hello World',
                                                                   'format': 'str'}}}}}],
             'name': 'test_name',
             'options': {'enabled': 'True',
                         'children': {},
                         'scheduler': {'args': {'hours': '*', 'minutes': '*/0.1', 'day': '*', 'month': '11-12'},
                                       'type': 'cron',
                                       'autorun': 'false'}}}

    def tearDown(self):
        flask_server.running_context.controller.workflows = {}
        workflows = [path.splitext(workflow)[0]
                     for workflow in os.listdir(core.config.paths.workflows_path) if workflow.endswith('.workflow')]
        matching_workflows = [workflow for workflow in workflows if
                              workflow in ['test_name', 'test_name2', 'helloWorldWorkflow']]

        # cleanup
        for workflow in matching_workflows:
            os.remove(path.join(core.config.paths.workflows_path, '{0}.workflow'.format(workflow)))

        if 'editedPlaybookName' in workflows:
            os.rename(path.join(core.config.paths.workflows_path, 'editedPlaybookName.workflow'),
                      path.join(core.config.paths.workflows_path, 'test.workflow'))
        if 'test.workflow' in os.listdir(core.config.paths.workflows_path):
            os.remove(os.path.join(core.config.paths.workflows_path, 'test.workflow'))
        os.rename(os.path.join(core.config.paths.workflows_path, 'test_copy.workflow_bkup'),
                  os.path.join(core.config.paths.workflows_path, 'test.workflow'))

    def test_display_all_playbooks(self):
        response = get_with_status_check(self, self.app, '/playbook', 'success', headers=self.headers)
        self.assertIn('playbooks', response)
        self.assertDictEqual(response['playbooks'], {'test': ['helloWorldWorkflow']})

    def test_display_playbook_workflows(self):
        response = get_with_status_check(self, self.app, '/playbook/test', 'success', headers=self.headers)
        self.assertIn('workflows', response)
        self.assertListEqual(response['workflows'], ['helloWorldWorkflow'])

    def test_display_playbook_workflows_invalid_name(self):
        get_with_status_check(self, self.app, '/playbook/junkName', 'error: name not found', headers=self.headers)

    def test_display_available_workflow_templates(self):
        response = get_with_status_check(self, self.app, '/playbook/templates', 'success', headers=self.headers)
        self.assertIn('templates', response)
        self.assertDictEqual(response['templates'], {'basicWorkflow': ['helloWorldWorkflow'],
                                                     'emptyWorkflow': ['emptyWorkflow']})

    def test_display_workflow_cytoscape(self):
        workflow_filename = os.path.join(".", "tests", "testWorkflows", 'multiactionWorkflowTest.workflow')
        flask_server.running_context.controller.load_workflows_from_file(path=workflow_filename)
        workflow = flask_server.running_context.controller.get_workflow('multiactionWorkflowTest',
                                                                        'multiactionWorkflow')
        steps_data = workflow.get_cytoscape_data()
        options_data = workflow.options.as_json()
        expected_response = {'status': 'success',
                             'steps': steps_data,
                             'options': options_data}
        response = get_with_status_check(self, self.app,
                                         '/playbook/multiactionWorkflowTest/multiactionWorkflow/display', 'success',
                                         headers=self.headers)
        self.assertDictEqual(response, expected_response)

    def test_display_workflow_element(self):
        workflow_filename = os.path.join(".", "tests", "testWorkflows", 'multiactionWorkflowTest.workflow')
        flask_server.running_context.controller.load_workflows_from_file(path=workflow_filename)
        workflow = flask_server.running_context.controller.get_workflow('multiactionWorkflowTest',
                                                                        'multiactionWorkflow')
        ancestries_to_json = [([], {"steps": ['start', '1']}),
                              (['start'], workflow.steps['start'].as_json(with_children=False)),
                              (['1'], workflow.steps['1'].as_json(with_children=False)),
                              (['start', '1'], workflow.steps['start'].conditionals[0].as_json(with_children=False)),
                              (['start', '1', 'regMatch'],
                               workflow.steps['start'].conditionals[0].flags[0].as_json(with_children=False)),
                              (['start', '1', 'regMatch', 'length'],
                               workflow.steps['start'].conditionals[0].flags[0].filters[0].as_json())]
        for ancestry, expected_output in ancestries_to_json:
            data = {"ancestry": ancestry}
            response = get_with_status_check(self, self.app,
                                             '/playbook/multiactionWorkflowTest/multiactionWorkflow/display',
                                             'success',
                                             data=json.dumps(data),
                                             content_type='application/json',
                                             headers=self.headers)
            self.assertIn('element', response)
            orderless_list_compare(self, response['element'], expected_output)

    def test_display_workflow_element_not_found(self):
        workflow_filename = os.path.join(".", "tests", "testWorkflows", 'multiactionWorkflowTest.workflow')
        flask_server.running_context.controller.load_workflows_from_file(path=workflow_filename)

        ancestries = [['starta'],
                      ['1a'],
                      ['start', '1a'],
                      ['start', '1', 'regMatcha'],
                      ['start', '1', 'regMatch', 'lengtha']]
        for ancestry in ancestries:
            get_with_status_check(self, self.app, '/playbook/multiactionWorkflowTest/multiactionWorkflow/display',
                                  'error: element not found',
                                  data=json.dumps({"ancestry": ancestry}),
                                  content_type='application/json',
                                  headers=self.headers)

    def test_display_workflow_element_invalid_json(self):
        workflow_filename = os.path.join(".", "tests", "testWorkflows", 'multiactionWorkflowTest.workflow')
        flask_server.running_context.controller.load_workflows_from_file(path=workflow_filename)
        data = {"invalid_field_name": "grepgrepgrepspamsapmsapm"}
        get_with_status_check(self, self.app, '/playbook/multiactionWorkflowTest/multiactionWorkflow/display',
                              'error: malformed JSON',
                              data=json.dumps(data),
                              content_type='application/json',
                              headers=self.headers)

    def test_display_workflow_invalid_name(self):
        get_with_status_check(self, self.app, '/playbook/multiactionWorkflowTest/multiactionWorkflow/display',
                              'error: name not found',
                              headers=self.headers)

    def test_add_playbook_default(self):
        expected_playbooks = flask_server.running_context.controller.get_all_workflows()
        original_length = len(list(expected_playbooks.keys()))
        response = post_with_status_check(self, self.app, '/playbook/test_playbook/add', 'success',
                                          headers=self.headers)
        self.assertIn('playbooks', response)
        expected_playbooks['test_playbook'] = ['emptyWorkflow']
        self.assertDictEqual(response['playbooks'], expected_playbooks)
        self.assertDictEqual(flask_server.running_context.controller.get_all_workflows(), expected_playbooks)
        self.assertEqual(len(list(flask_server.running_context.controller.workflows)), original_length + 1)

    def test_add_playbook_template(self):
        expected_playbooks = flask_server.running_context.controller.get_all_workflows()
        data = {'playbook_template': 'basicWorkflow'}
        response = post_with_status_check(self, self.app, '/playbook/test_playbook/add', 'success',
                                          data=data, headers=self.headers)
        self.assertIn('playbooks', response)
        expected_playbooks['test_playbook'] = ['helloWorldWorkflow']
        self.assertDictEqual(response['playbooks'], expected_playbooks)
        self.assertDictEqual(flask_server.running_context.controller.get_all_workflows(), expected_playbooks)
        self.assertEqual(len(list(flask_server.running_context.controller.workflows)), 2)

    def test_add_playbook_template_invalid_name(self):
        expected_playbooks = flask_server.running_context.controller.get_all_workflows()
        data = {'playbook_template': 'junkPlaybookTemplate'}
        response = post_with_status_check(self, self.app, '/playbook/test_playbook/add',
                                          'warning: template playbook not found. Using default template',
                                          data=data, headers=self.headers)
        self.assertIn('playbooks', response)
        expected_playbooks['test_playbook'] = ['emptyWorkflow']
        self.assertDictEqual(response['playbooks'], expected_playbooks)
        self.assertDictEqual(flask_server.running_context.controller.get_all_workflows(), expected_playbooks)
        self.assertEqual(len(list(flask_server.running_context.controller.workflows)), 2)

    def test_add_workflow(self):
        initial_workflows = list(flask_server.running_context.controller.workflows.keys())
        workflow_name = 'test_name'
        response = post_with_status_check(self, self.app, '/playbook/test/{0}/add'.format(workflow_name), 'success',
                                          headers=self.headers)
        self.assertDictEqual(response, self.empty_workflow_json)

        final_workflows = flask_server.running_context.controller.workflows.keys()
        self.assertEqual(len(final_workflows), len(initial_workflows) + 1)
        self.assertTrue(flask_server.running_context.controller.is_workflow_registered('test', 'test_name'))

    def test_add_templated_workflow(self):
        initial_workflows = list(flask_server.running_context.controller.workflows.keys())
        workflow_name = 'test_name'
        data = {"playbook": 'basicWorkflow',
                "template": 'helloWorldWorkflow'}
        response = post_with_status_check(self, self.app, '/playbook/test/{0}/add'.format(workflow_name), 'success',
                                          data=data, headers=self.headers)
        self.assertIn('workflow', response)
        self.assertDictEqual(response['workflow'], self.hello_world_json)

        final_workflows = flask_server.running_context.controller.workflows.keys()
        self.assertEqual(len(final_workflows), len(initial_workflows) + 1)
        self.assertTrue(flask_server.running_context.controller.is_workflow_registered('test', 'test_name'))

    def test_add_templated_workflow_invalid_template(self):
        initial_workflows = list(flask_server.running_context.controller.workflows.keys())
        workflow_name = 'test_name'
        data = {"playbook": 'basicWorkflow',
                "template": "junktemplatename"}
        response = self.app.post('/playbook/test/{0}/add'.format(workflow_name), data=data, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        response = json.loads(response.get_data(as_text=True))
        self.empty_workflow_json['status'] = 'warning: template not found in playbook. Using default template'
        self.assertDictEqual(response, self.empty_workflow_json)

        final_workflows = flask_server.running_context.controller.workflows.keys()
        self.assertEqual(len(final_workflows), len(initial_workflows) + 1)
        self.assertTrue(flask_server.running_context.controller.is_workflow_registered('test', 'test_name'))

    def test_add_templated_workflow_invalid_template_playbook(self):
        initial_workflows = list(flask_server.running_context.controller.workflows.keys())
        workflow_name = 'test_name'
        data = {"playbook": 'junkTemplatePlaybook',
                "template": "helloWorldWorkflow"}
        response = self.app.post('/playbook/test/{0}/add'.format(workflow_name), data=data, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        response = json.loads(response.get_data(as_text=True))
        self.empty_workflow_json['status'] = 'warning: template playbook not found. Using default template'
        self.assertDictEqual(response, self.empty_workflow_json)

        final_workflows = flask_server.running_context.controller.workflows.keys()
        self.assertEqual(len(final_workflows), len(initial_workflows) + 1)
        self.assertTrue(flask_server.running_context.controller.is_workflow_registered('test', 'test_name'))

    def test_edit_playbook(self):
        expected_keys = flask_server.running_context.controller.get_all_workflows()
        new_playbook_name = 'editedPlaybookName'
        data = {'new_name': new_playbook_name}
        response = post_with_status_check(self, self.app, '/playbook/test/edit', 'success',
                                          data=data, headers=self.headers)
        expected_keys['editedPlaybookName'] = expected_keys.pop('test')
        self.assertIn('playbooks', response)
        self.assertDictEqual(response['playbooks'], expected_keys)
        self.assertDictEqual(flask_server.running_context.controller.get_all_workflows(), expected_keys)

        self.assertTrue(
            os.path.isfile(os.path.join(core.config.paths.workflows_path, 'editedPlaybookName.workflow')))
        self.assertFalse(os.path.isfile(os.path.join(core.config.paths.workflows_path, 'test.workflow')))

    def test_edit_playbook_no_name(self):
        expected_keys = flask_server.running_context.controller.get_all_workflows()
        response = post_with_status_check(self, self.app, '/playbook/test/edit', 'error: invalid form',
                                          headers=self.headers)
        self.assertIn('playbooks', response)
        self.assertDictEqual(response['playbooks'], expected_keys)
        self.assertDictEqual(flask_server.running_context.controller.get_all_workflows(), expected_keys)
        self.assertTrue(os.path.isfile(os.path.join(core.config.paths.workflows_path, 'test.workflow')))

    def test_edit_playbook_invalid_name(self):
        expected_keys = flask_server.running_context.controller.get_all_workflows()
        response = post_with_status_check(self, self.app, '/playbook/junkPlaybookName/edit',
                                          'error: playbook name not found', headers=self.headers)
        self.assertIn('playbooks', response)
        self.assertDictEqual(response['playbooks'], expected_keys)
        self.assertDictEqual(flask_server.running_context.controller.get_all_workflows(), expected_keys)

        self.assertFalse(
            os.path.isfile(os.path.join(core.config.paths.workflows_path, 'junkPlaybookName.workflow')))
        self.assertTrue(os.path.isfile(os.path.join(core.config.paths.workflows_path, 'test.workflow')))

    def test_edit_playbook_no_file(self):
        self.app.post('/playbook/test2/add', headers=self.headers)
        expected_keys = flask_server.running_context.controller.get_all_workflows()
        new_playbook_name = 'editedPlaybookName'
        data = {'new_name': new_playbook_name}
        response = post_with_status_check(self, self.app, '/playbook/test2/edit', 'success',
                                          data=data, headers=self.headers)
        expected_keys['editedPlaybookName'] = expected_keys.pop('test2')
        self.assertIn('playbooks', response)
        self.assertDictEqual(response['playbooks'], expected_keys)
        self.assertDictEqual(flask_server.running_context.controller.get_all_workflows(), expected_keys)

        self.assertFalse(os.path.isfile(os.path.join(core.config.paths.workflows_path, 'test2.workflow')))
        self.assertFalse(
            os.path.isfile(os.path.join(core.config.paths.workflows_path, 'editedPlaybookName.workflow')))
        self.assertTrue(os.path.isfile(os.path.join(core.config.paths.workflows_path, 'test.workflow')))

    def test_edit_workflow_name_only(self):
        workflow_name = 'test_name'
        data = {"new_name": workflow_name}
        response = post_with_status_check(self, self.app, '/playbook/test/helloWorldWorkflow/edit', 'success',
                                          data=data, headers=self.headers)
        expected_json = {'status': 'success',
                         'workflow': {'name': 'test_name',
                                      'options': {'enabled': 'False',
                                                  'children': {},
                                                  'scheduler': {'args': {},
                                                                'type': 'chron',
                                                                'autorun': 'false'}}}}

        self.assertDictEqual(response, expected_json)

        self.assertEqual(len(flask_server.running_context.controller.workflows.keys()), 1)
        self.assertTrue(flask_server.running_context.controller.is_workflow_registered('test', 'test_name'))
        self.assertFalse(
            flask_server.running_context.controller.is_workflow_registered('test', 'helloWorldWorkflow'))

    def test_edit_workflow_options_only(self):
        expected_args = json.dumps({"arg1": "val1", "arg2": "val2", "agr3": "val3"})
        data = {"enabled": "true",
                "scheduler_type": "test_scheduler",
                "autoRun": 'true',
                "scheduler_args": expected_args}
        response = post_with_status_check(self, self.app, '/playbook/test/helloWorldWorkflow/edit', 'success',
                                          data=data, headers=self.headers)
        expected_json = {'status': 'success',
                         'workflow': {'name': 'helloWorldWorkflow',
                                      'options': {'enabled': 'True',
                                                  'children': {},
                                                  'scheduler': {'args': {'arg1': 'val1',
                                                                         'arg2': 'val2',
                                                                         'agr3': 'val3'},
                                                                'type': 'test_scheduler',
                                                                'autorun': 'true'}}}}
        self.assertDictEqual(response, expected_json)

        options = flask_server.running_context.controller.get_workflow('test', 'helloWorldWorkflow').options
        self.assertTrue(options.enabled)
        self.assertEqual(options.scheduler['type'], 'test_scheduler')
        self.assertEqual(options.scheduler['autorun'], 'true')
        self.assertEqual(options.scheduler['args'], json.loads(expected_args))
        self.assertTrue(
            flask_server.running_context.controller.is_workflow_registered('test', 'helloWorldWorkflow'))

    def test_edit_workflow_(self):
        expected_args = json.dumps({"arg1": "val1", "arg2": "val2", "agr3": "val3"})
        workflow_name = 'test_name'
        data = {"new_name": workflow_name,
                "enabled": "true",
                "scheduler_type": "test_scheduler",
                "autoRun": 'true',
                "scheduler_args": expected_args}
        response = post_with_status_check(self, self.app, '/playbook/test/helloWorldWorkflow/edit', 'success',
                                          data=data, headers=self.headers)
        expected_json = {'status': 'success',
                         'workflow': {'name': u'test_name',
                                      'options': {'enabled': 'True',
                                                  'children': {},
                                                  'scheduler': {'args': {'arg1': 'val1',
                                                                         'arg2': 'val2',
                                                                         'agr3': 'val3'},
                                                                'type': 'test_scheduler',
                                                                'autorun': 'true'}}}}
        self.assertDictEqual(response, expected_json)

        options = flask_server.running_context.controller.get_workflow('test', workflow_name).options
        self.assertTrue(options.enabled)
        self.assertEqual(options.scheduler['type'], 'test_scheduler')
        self.assertEqual(options.scheduler['autorun'], 'true')
        self.assertEqual(options.scheduler['args'], json.loads(expected_args))
        self.assertTrue(flask_server.running_context.controller.is_workflow_registered('test', 'test_name'))
        self.assertFalse(
            flask_server.running_context.controller.is_workflow_registered('test', 'helloWorldWorkflow'))

    def test_edit_workflow_invalid_workflow(self):
        workflow_name = 'test_name'
        data = {"new_name": workflow_name}
        initial_workflows = flask_server.running_context.controller.workflows.keys()
        post_with_status_check(self, self.app, '/playbook/test/junkworkflow/edit',
                               'error: workflow name is not valid',
                               data=data, headers=self.headers)
        final_workflows = flask_server.running_context.controller.workflows.keys()
        self.assertSetEqual(set(final_workflows), set(initial_workflows))

    def test_save_workflow(self):
        workflow_name = list(flask_server.running_context.controller.workflows.keys())[0].workflow
        initial_workflow = flask_server.running_context.controller.get_workflow('test', workflow_name)
        initial_steps = dict(initial_workflow.steps)
        initial_workflow_cytoscape = list(initial_workflow.get_cytoscape_data())
        added_step_cytoscape = {'data': {'id': 'new_id',
                                         'parameters': {'errors': [],
                                                        'name': 'new_id',
                                                        'app': 'new_app',
                                                        'next': [],
                                                        'device': 'new_device',
                                                        'action': 'new_action',
                                                        'input': {}}},
                                'group': 'nodes'}
        initial_workflow_cytoscape.insert(0, added_step_cytoscape)
        data = {"cytoscape": json.dumps(initial_workflow_cytoscape)}
        post_with_status_check(self, self.app, '/playbook/test/{0}/save'.format(workflow_name), 'success',
                               data=json.dumps(data),
                               headers=self.headers,
                               content_type='application/json')

        resulting_workflow = flask_server.running_context.controller.get_workflow('test', workflow_name)

        # compare the steps in initial and final workflow
        self.assertEqual(len(resulting_workflow.steps.keys()), len(list(initial_steps.keys())) + 1)
        for step_name, initial_step in initial_steps.items():
            self.assertIn(step_name, resulting_workflow.steps.keys())
            self.assertDictEqual(initial_step.as_json(), resulting_workflow.steps[step_name].as_json())

        # assert that the file has been saved to a file
        workflows = [path.splitext(workflow)[0]
                     for workflow in os.listdir(core.config.paths.workflows_path) if workflow.endswith('.workflow')]
        matching_workflows = [workflow for workflow in workflows if workflow == 'test']
        self.assertEqual(len(matching_workflows), 1)

        # assert that the file loads properly after being saved
        flask_server.running_context.controller.workflows = {}
        flask_server.running_context.controller.load_workflows_from_file(os.path.join(core.config.paths.workflows_path,
                                                                                   'test.workflow'))
        orderless_list_compare(self,
                               [key.workflow for key in flask_server.running_context.controller.workflows.keys()],
                               ['helloWorldWorkflow'])
        loaded_workflow = flask_server.running_context.controller.get_workflow('test', workflow_name)

        # compare the steps in loaded and expected workflow
        self.assertEqual(len(loaded_workflow.steps.keys()), len(list(resulting_workflow.steps.keys())))
        for step_name, loaded_step in loaded_workflow.steps.items():
            self.assertIn(step_name, resulting_workflow.steps.keys())
            self.assertDictEqual(loaded_step.as_json(), resulting_workflow.steps[step_name].as_json())

    def test_save_workflow_invalid_name(self):
        post_with_status_check(self, self.app, '/playbook/test/junkworkflowname/save',
                               'error: workflow name is not valid', headers=self.headers)

    def test_delete_playbook(self):
        response = post_with_status_check(self, self.app, '/playbook/test/delete', 'success', headers=self.headers)
        self.assertDictEqual(response, {'status': 'success', 'playbooks': {}})

        self.assertFalse(flask_server.running_context.controller.is_playbook_registered('test'))

        playbooks = [os.path.splitext(playbook)[0]
                     for playbook in helpers.locate_workflows_in_directory(core.config.paths.workflows_path)]
        self.assertEqual(len(playbooks), 0)

    def test_delete_playbook_no_file(self):
        initial_playbooks = flask_server.running_context.controller.get_all_workflows()
        initial_playbook_files = [os.path.splitext(playbook)[0] for playbook in
                                  helpers.locate_workflows_in_directory()]
        self.app.post('/playbook/test_playbook/add', headers=self.headers)
        response = post_with_status_check(self, self.app, '/playbook/test_playbook/delete', 'success',
                                          headers=self.headers)
        self.assertDictEqual(response, {'status': 'success', 'playbooks': initial_playbooks})

        self.assertTrue(flask_server.running_context.controller.is_playbook_registered('test'))
        self.assertFalse(flask_server.running_context.controller.is_playbook_registered('test_playbook'))

        final_playbook_files = [os.path.splitext(playbook)[0] for playbook in
                                helpers.locate_workflows_in_directory()]
        orderless_list_compare(self, final_playbook_files, initial_playbook_files)

    def test_delete_playbook_invalid_name(self):
        initial_playbooks = flask_server.running_context.controller.get_all_workflows()
        initial_playbook_files = [os.path.splitext(playbook)[0] for playbook in
                                  helpers.locate_workflows_in_directory()]
        response = post_with_status_check(self, self.app, '/playbook/junkPlaybookName/delete', 'success',
                                          headers=self.headers)
        self.assertDictEqual(response, {'status': 'success', 'playbooks': initial_playbooks})
        self.assertFalse(flask_server.running_context.controller.is_playbook_registered('junkPlaybookName'))
        final_playbook_files = [os.path.splitext(playbook)[0] for playbook in
                                helpers.locate_workflows_in_directory()]
        orderless_list_compare(self, final_playbook_files, initial_playbook_files)

    def test_delete_workflow(self):
        workflow_name = 'test_name2'
        self.app.post('/playbook/test/{0}/add'.format(workflow_name), headers=self.headers)
        cytoscape_data = flask_server.running_context.controller.get_workflow('test',
                                                                              'helloWorldWorkflow').get_cytoscape_data()
        data = {'cytoscape': json.dumps(cytoscape_data)}
        self.app.post('/playbook/test/{0}/save'.format(workflow_name),
                      data=json.dumps(data),
                      headers=self.headers,
                      content_type='application/json')
        response = post_with_status_check(self, self.app, '/playbook/test/{0}/delete'.format(workflow_name), 'success',
                                          headers=self.headers)
        self.assertSetEqual(set(list(response.keys())), set(list(['status', 'playbooks'])))
        self.assertEqual(response['status'], 'success')
        self.assertDictEqual(response['playbooks'], {'test': ['helloWorldWorkflow']})

        self.assertFalse(flask_server.running_context.controller.is_workflow_registered('test', workflow_name))

    def test_delete_workflow_invalid(self):
        workflow_name = 'junkworkflowname'
        response = post_with_status_check(self, self.app, '/playbook/test/{0}/delete'.format(workflow_name),
                                          'error: invalid workflow name',
                                          headers=self.headers)
        self.assertSetEqual(set(list(response.keys())), set(list(['status', 'playbooks'])))
        self.assertDictEqual(response['playbooks'], {'test': ['helloWorldWorkflow']})

        self.assertFalse(flask_server.running_context.controller.is_workflow_registered('test', workflow_name))

    def test_invalid_operation_on_playbook_crud(self):
        post_with_status_check(self, self.app, '/playbook/junkPlaybookName/junkOperation', 'error: invalid operation',
                               headers=self.headers)

    def test_invalid_operation_on_workflow_crud(self):
        post_with_status_check(self, self.app, '/playbook/junkPlaybookName/helloWorldWorkflow/junkOperation',
                               'error: invalid operation',
                               headers=self.headers)

    def test_display_flags(self):
        expected_flags = ['count', 'regMatch']
        response = get_with_status_check(self, self.app, '/flags', 'success', headers=self.headers)
        orderless_list_compare(self, list(response['flags'].keys()), expected_flags)

    def test_display_filters(self):
        expected_flags = ['length']
        response = get_with_status_check(self, self.app, '/filters', 'success', headers=self.headers)
        orderless_list_compare(self, list(response['filters'].keys()), expected_flags)