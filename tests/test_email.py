from unittest import TestCase
from unittest.mock import patch, MagicMock, call, ANY

from flask import Flask
import arrow
from jinja2.exceptions import TemplateNotFound

from src.flask_site_framework.email import cli_email, test_email, EmailMessage, EmailPlugin


@patch('src.flask_site_framework.email.arrow.utcnow', return_value=arrow.get('2026-09-10 08:00:00'))
class TestTestEmailCommand(TestCase):
    def test_send(self, mock_utcnow):
        app = Flask(__name__)
        mock_email = MagicMock()
        app.email = mock_email
        with app.app_context(), app.test_request_context():
            app.config['SITE_NAME'] = 'foo'
            with self.assertRaises(SystemExit):
                test_email(['test@test.test'])
            subject = "Test email from foo - 2026-09-10"
            body = (
                "This is a test email sent from foo.\n"
                "It was sent at 2026-09-10T08:00:00+00:00 to test@test.test\n"
            )
            mock_email.create.assert_called_once_with(subject=subject, text_body=body, to=['test@test.test'])
            mock_email.create.return_value.send_message.assert_called_once_with()

    def test_send_with_template(self, mock_utcnow):
        app = Flask(__name__)
        mock_email = MagicMock()
        app.email = mock_email
        with app.app_context(), app.test_request_context():
            app.config['SITE_NAME'] = 'foo'
            with self.assertRaises(SystemExit):
                test_email(['test@test.test', '--template', 'test'])
            subject = "Test email from foo - 2026-09-10"
            body = (
                "This is a test email sent from foo.\n"
                "It was sent at 2026-09-10T08:00:00+00:00 to test@test.test\n"
            )
            mock_email.create.assert_called_once_with(subject=subject, to=['test@test.test'])
            mock_email.create.return_value.render.assert_called_once_with('test', subject=subject, to=['test@test.test'], body=body)
            mock_email.create.return_value.render.return_value.send_message.assert_called_once_with()


@patch('src.flask_site_framework.email.Message.__init__')
class TestEmailMessage_Init(TestCase):
    def test_init(self, mock_super_init):
        m = EmailMessage('plugin', 'foo', bar='baz')
        self.assertEqual(m.plugin, 'plugin')
        mock_super_init.assert_called_once_with('foo', bar='baz')


@patch('src.flask_site_framework.email.render_template')
class TestEmailMessage_RenderCandidate(TestCase):
    def test_render_not_found(self, mock_render_template):
        mock_render_template.side_effect = TemplateNotFound('tpl')
        candidates = ['foo', 'bar', 'baz']
        res = EmailMessage._render_candidate(candidates)
        self.assertIsNone(res)
        mock_render_template.assert_has_calls([
            call('foo'),
            call('bar'),
            call('baz'),
        ])

    def test_render(self, mock_render_template):
        mock_render_template.side_effect = [TemplateNotFound('tpl'), 'test']
        candidates = ['foo', 'bar', 'baz']
        res = EmailMessage._render_candidate(candidates)
        self.assertEqual(res, 'test')
        mock_render_template.assert_has_calls([
            call('foo'),
            call('bar'),
        ])

    def test_render_extra_args(self, mock_render_template):
        mock_render_template.side_effect = [TemplateNotFound('tpl'), 'test']
        candidates = ['foo', 'bar', 'baz']
        res = EmailMessage._render_candidate(candidates, 'foo', bar='baz')
        self.assertEqual(res, 'test')
        mock_render_template.assert_has_calls([
            call('foo', 'foo', bar='baz'),
            call('bar', 'foo', bar='baz'),
        ])


@patch('src.flask_site_framework.email.Message.html')
@patch('src.flask_site_framework.email.Message.__init__')
@patch('src.flask_site_framework.email.EmailMessage._render_candidate')
@patch('src.flask_site_framework.email.markdown')
class TestEmailMessage_Render(TestCase):
    def test_render_not_found(self, mock_markdown, mock_render_candidate, mock_msg_init, mock_msg_html):
        mock_render_candidate.return_value = None
        m = EmailMessage('plugin')
        m.body = m.html = None
        with self.assertRaisesRegex(RuntimeError, 'template candidates'):
            m.render('testtemplate')
        mock_render_candidate.assert_has_calls([
            call(['email/testtemplate/markdown.j2', 'email/testtemplate.md.j2']),
            call(['email/testtemplate/html.j2', 'email/testtemplate.html.j2']),
        ])
        mock_markdown.assert_not_called()
        self.assertIsNone(m.body)
        self.assertIsNone(m.html)

    def test_render_no_text(self, mock_markdown, mock_render_candidate, mock_msg_init, mock_msg_html):
        mock_render_candidate.side_effect = [None, 'htmlbody']
        m = EmailMessage('plugin')
        m.body = m.html = None
        self.assertEqual(m.render('testtemplate'), m)
        mock_render_candidate.assert_has_calls([
            call(['email/testtemplate/markdown.j2', 'email/testtemplate.md.j2']),
            call(['email/testtemplate/html.j2', 'email/testtemplate.html.j2']),
        ])
        mock_markdown.assert_not_called()
        self.assertIsNone(m.body)
        self.assertEqual(m.html, 'htmlbody')

    def test_render_no_html(self, mock_markdown, mock_render_candidate, mock_msg_init, mock_msg_html):
        mock_render_candidate.side_effect = ['textbody', None]
        m = EmailMessage('plugin')
        m.body = m.html = None
        self.assertEqual(m.render('testtemplate'), m)
        mock_render_candidate.assert_has_calls([
            call(['email/testtemplate/markdown.j2', 'email/testtemplate.md.j2']),
            call(['email/testtemplate/html.j2', 'email/testtemplate.html.j2']),
        ])
        mock_markdown.assert_called_once_with('textbody')
        self.assertEqual(m.body, 'textbody')
        self.assertEqual(m.html, mock_markdown.return_value)

    def test_render_text_and_html(self, mock_markdown, mock_render_candidate, mock_msg_init, mock_msg_html):
        mock_render_candidate.side_effect = ['textbody', 'htmlbody']
        m = EmailMessage('plugin')
        m.body = m.html = None
        self.assertEqual(m.render('testtemplate'), m)
        mock_render_candidate.assert_has_calls([
            call(['email/testtemplate/markdown.j2', 'email/testtemplate.md.j2']),
            call(['email/testtemplate/html.j2', 'email/testtemplate.html.j2']),
        ])
        mock_markdown.assert_not_called()
        self.assertEqual(m.body, 'textbody')
        self.assertEqual(m.html, 'htmlbody')

    def test_render_extra_args(self, mock_markdown, mock_render_candidate, mock_msg_init, mock_msg_html):
        mock_render_candidate.side_effect = ['textbody', 'htmlbody']
        m = EmailMessage('plugin')
        m.body = m.html = None
        self.assertEqual(m.render('testtemplate', 'foo', text_args={'textarg': 'val1'}, html_args={'htmlarg': 'val2'}, bar='baz'), m)
        mock_render_candidate.assert_has_calls([
            call(['email/testtemplate/markdown.j2', 'email/testtemplate.md.j2'], 'foo', textarg='val1', bar='baz'),
            call(['email/testtemplate/html.j2', 'email/testtemplate.html.j2'], 'foo', htmlarg='val2', bar='baz'),
        ])
        mock_markdown.assert_not_called()
        self.assertEqual(m.body, 'textbody')
        self.assertEqual(m.html, 'htmlbody')


@patch('src.flask_site_framework.email.Message.html')
@patch('src.flask_site_framework.email.Message.__init__')
class TestEmailMessage_SendMessage(TestCase):
    def test_send_no_text_or_html(self, mock_msg_init, mock_msg_html):
        mock_plugin = MagicMock()
        m = EmailMessage(mock_plugin)
        m.body = m.html = m.recipients = m.cc = m.bcc = None
        m.recipients = 'foo'
        with self.assertRaisesRegex(ValueError, 'body'):
            m.send_message()
        mock_plugin.send_email.assert_not_called()

    def test_send_no_recipients(self, mock_msg_init, mock_msg_html):
        mock_plugin = MagicMock()
        m = EmailMessage(mock_plugin)
        m.body = m.html = m.recipients = m.cc = m.bcc = None
        m.body = 'foo'
        with self.assertRaisesRegex(ValueError, 'Recipients'):
            m.send_message()
        mock_plugin.send_email.assert_not_called()

    def test_send_only_recipients(self, mock_msg_init, mock_msg_html):
        mock_plugin = MagicMock()
        m = EmailMessage(mock_plugin)
        m.body = m.html = m.recipients = m.cc = m.bcc = None
        m.body = 'foo'
        m.recipients = 'testrecip'
        m.send_message()
        mock_plugin.send_email.assert_called_once_with(m)

    def test_send_only_cc(self, mock_msg_init, mock_msg_html):
        mock_plugin = MagicMock()
        m = EmailMessage(mock_plugin)
        m.body = m.html = m.recipients = m.cc = m.bcc = None
        m.body = 'foo'
        m.cc = 'testrecip'
        m.send_message()
        mock_plugin.send_email.assert_called_once_with(m)

    def test_send_only_bcc(self, mock_msg_init, mock_msg_html):
        mock_plugin = MagicMock()
        m = EmailMessage(mock_plugin)
        m.body = m.html = m.recipients = m.cc = m.bcc = None
        m.body = 'foo'
        m.bcc = 'testrecip'
        m.send_message()
        mock_plugin.send_email.assert_called_once_with(m)


class TestEmailPlugin_GetConfig(TestCase):
    def test_get_config(self):
        p = EmailPlugin()
        self.assertGreater(len(p.get_config()), 0)


@patch('src.flask_site_framework.email.Mail')
class TestEmailPlugin_GetFlaskPlugins(TestCase):
    def test_get_flask_plugins(self, mock_mail):
        p = EmailPlugin()
        res = p.get_flask_plugins()
        self.assertEqual(p.mail, mock_mail.return_value)
        self.assertEqual(res, [p.mail])


class TestEmailPlugin_GetCommands(TestCase):
    def test_get_commands(self):
        p = EmailPlugin()
        res = p.get_commands()
        self.assertEqual(res, [cli_email])

@patch('src.flask_site_framework.email.EmailMessage')
class TestEmailPlugin_Create(TestCase):
    def test_create_no_args(self, mock_msg):
        p = EmailPlugin()
        res = p.create('subj')
        self.assertEqual(res, mock_msg.return_value)
        mock_msg.assert_called_once_with(
            p,
            subject='subj',
            recipients=None,
            body=None,
            html=None,
            sender=None,
            cc=None,
            bcc=None,
            reply_to=None,
        )

    def test_create_with_args(self, mock_msg):
        p = EmailPlugin()
        res = p.create(
            'subj',
            text_body='textbody',
            html_body='htmlbody',
            sender='test@test.test',
            to=['test1@test.test'],
            reply_to=['test2@test.test'],
            cc=['test3@test.test'],
            bcc=['tes4@test.test'],
        )
        self.assertEqual(res, mock_msg.return_value)
        mock_msg.assert_called_once_with(
            p,
            subject='subj',
            body='textbody',
            html='htmlbody',
            sender='test@test.test',
            recipients=['test1@test.test'],
            reply_to=['test2@test.test'],
            cc=['test3@test.test'],
            bcc=['tes4@test.test'],
        )


class TestEmailPlugin_SendEmail(TestCase):
    def test_send_email(self):
        p = EmailPlugin()
        p.mail = MagicMock()
        msg = MagicMock()
        res = p.send_email(msg)
        self.assertEqual(res, p.mail.send.return_value)
        p.mail.send.assert_called_once_with(msg)


# @patch('src.flask_site_framework.tabulate')
# class TestListConfig(TestCase):
#     def test_list_config(self, mock_tabulate):
#         # Prevent errant data from being printed
#         mock_tabulate.return_value = ''
#         app = Flask(__name__)
#         # Prevent loading actual config here otherwise it will fail
#         with patch('src.flask_site_framework.FlaskConfigPlugin.init_app'):
#             p = FlaskConfigPlugin(app)
#         with app.app_context(), app.test_request_context():
#             app._config = {
#                 'FOO': {
#                     'default': 'bar',
#                     'required': True,
#                     'description': 'asdf',
#                 }
#             }
#             app.config = {'FOO': 'baz'}
#             with self.assertRaises(SystemExit):
#                 list_config()
#             mock_tabulate.assert_called_once_with(
#                 [['FOO', True, 'bar', 'baz', 'asdf']],
#                 headers=['Key', 'Required', 'Default Value', 'Set Value', 'Description']
#             )


# @patch('src.flask_site_framework.Plugin.__init__')
# class TestInit(TestCase):
#     def test_super_called(self, mock_super_init):
#         p = FlaskConfigPlugin()
#         mock_super_init.assert_called_once_with(app=None, url_prefix=None)
#         self.assertEqual(p.env_prefix, 'FLASK')
    
#     def test_super_called_with_args_env_prefix_set(self, mock_super_init):
#         p = FlaskConfigPlugin(app='foo', url_prefix='bar', env_prefix='baz')
#         mock_super_init.assert_called_once_with(app='foo', url_prefix='bar')
#         self.assertEqual(p.env_prefix, 'baz')


# class TestGetConfig(TestCase):
#     def test_value_returned(self):
#         p = FlaskConfigPlugin()
#         self.assertGreater(len(p.get_config()), 0)


# class TestGetCommands(TestCase):
#     def test_get_commands(self):
#         p = FlaskConfigPlugin()
#         self.assertEqual(p.get_commands(), [cli_config])


# @patch('src.flask_site_framework.load_dotenv')
# @patch('src.flask_site_framework.Plugin.init_app')
# class TestInitApp(TestCase):
#     def test_calls(self, mock_init_app, mock_load_dotenv):
#         p = FlaskConfigPlugin()
#         mock_app = MagicMock()
#         p.init_app(mock_app)
#         mock_load_dotenv.assert_called_once_with()
#         mock_app.config.from_prefixed_env.assert_called_once_with(p.env_prefix)
#         mock_init_app.assert_called_once_with(mock_app)

#     def test_call_order(self, mock_init_app, mock_load_dotenv):
#         p = FlaskConfigPlugin()
#         calls = []
#         def mock_call(name):
#             def mock_call_impl(*a, **ka):
#                 calls.append(name)
#             return mock_call_impl
#         mock_app = MagicMock()
#         mock_load_dotenv.side_effect = mock_call('load_dotenv')
#         mock_app.config.from_prefixed_env.side_effect = mock_call('from_prefixed_env')
#         mock_init_app.side_effect = mock_call('init_app')
#         p.init_app(mock_app)
#         self.assertEqual(calls, ['load_dotenv', 'from_prefixed_env', 'init_app'])
