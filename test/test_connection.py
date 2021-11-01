from datalink.connection import Connection
from datalink.api_config import ApiConfig
from datalink.errors.datalink_error import (
    DatalinkError, LimitExceededError, InternalServerError,
    AuthenticationError, ForbiddenError, InvalidRequestError,
    NotFoundError, ServiceUnavailableError)
from test.test_retries import ModifyRetrySettingsTestCase
from test.helpers.httpretty_extension import httpretty
import json
from mock import patch, call
from datalink.version import VERSION
from parameterized import parameterized


class ConnectionTest(ModifyRetrySettingsTestCase):

    def setUp(self):
        httpretty.enable()

    def tearDown(self):
        httpretty.disable()

    @parameterized.expand(['GET', 'POST'])
    def test_datalink_exceptions_no_retries(self, request_method):
        ApiConfig.use_retries = False
        datalink_errors = [('QELx04', 429, LimitExceededError),
                         ('QEMx01', 500, InternalServerError),
                         ('QEAx01', 400, AuthenticationError),
                         ('QEPx02', 403, ForbiddenError),
                         ('QESx03', 422, InvalidRequestError),
                         ('QECx05', 404, NotFoundError),
                         ('QEXx01', 503, ServiceUnavailableError),
                         ('QEZx02', 400, DatalinkError)]

        httpretty.register_uri(getattr(httpretty, request_method),
                               "https://data.nasdaq.com/api/v3/databases",
                               responses=[httpretty.Response(body=json.dumps(
                                   {'datalink_error':
                                    {'code': x[0], 'message': 'something went wrong'}}),
                                   status=x[1]) for x in datalink_errors]
                               )

        for expected_error in datalink_errors:
            self.assertRaises(
                expected_error[2], lambda: Connection.request(request_method, 'databases'))

    @parameterized.expand(['GET', 'POST'])
    def test_parse_error(self, request_method):
        ApiConfig.retry_backoff_factor = 0
        httpretty.register_uri(getattr(httpretty, request_method),
                               "https://data.nasdaq.com/api/v3/databases",
                               body="not json", status=500)
        self.assertRaises(
            DatalinkError, lambda: Connection.request(request_method, 'databases'))

    @parameterized.expand(['GET', 'POST'])
    def test_non_datalink_error(self, request_method):
        ApiConfig.retry_backoff_factor = 0
        httpretty.register_uri(getattr(httpretty, request_method),
                               "https://data.nasdaq.com/api/v3/databases",
                               body=json.dumps(
                                {'foobar':
                                 {'code': 'blah', 'message': 'something went wrong'}}), status=500)
        self.assertRaises(
            DatalinkError, lambda: Connection.request(request_method, 'databases'))

    @parameterized.expand(['GET', 'POST'])
    @patch('datalink.connection.Connection.execute_request')
    def test_build_request(self, request_method, mock):
        ApiConfig.api_key = 'api_token'
        ApiConfig.api_version = '2015-04-09'
        params = {'per_page': 10, 'page': 2}
        headers = {'x-custom-header': 'header value'}
        Connection.request(request_method, 'databases', headers=headers, params=params)
        expected = call(request_method, 'https://data.nasdaq.com/api/v3/databases',
                        headers={'x-custom-header': 'header value',
                                 'x-api-token': 'api_token',
                                 'accept': ('application/json, '
                                            'application/vnd.data.nasdaq+json;version=2015-04-09'),
                                 'request-source': 'python',
                                 'request-source-version': VERSION},
                        params={'per_page': 10, 'page': 2})
        self.assertEqual(mock.call_args, expected)
