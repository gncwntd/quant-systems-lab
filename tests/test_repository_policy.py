"""Exercise publication boundaries independently of the current source tree."""

import importlib.util
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    'repository_policy', Path(__file__).resolve().parents[1] / 'tools' / 'check_repository.py'
)
policy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(policy)


class PublicationPolicyTests(unittest.TestCase):
    def test_local_and_sensitive_files_are_rejected(self):
        for name in ('.local/planning/README.md', '.env', 'core/.env.prod',
                     'tests/raw.csv', 'docs/account.key', 'data/ticks.txt', 'mt5/bridge.ex5'):
            with self.subTest(name=name):
                self.assertTrue(policy.path_errors(name))

    def test_regular_public_files_and_placeholders_are_allowed(self):
        for name in ('README.md', '.env.example', 'tests/fixtures/event.json',
                     'core/parser.c', '.github/workflows/ci.yml', 'mt5/QSLQuoteBridge.mq5'):
            with self.subTest(name=name):
                self.assertEqual([], policy.path_errors(name))
        self.assertTrue(policy.path_errors('docs/link.md', '120000'))

    def test_sensitive_content_is_detected_without_echoing_value(self):
        token = 'gh' + 'p_' + 'x' * 36
        errors = policy.content_errors('core/a.c', (token + '\n').encode())
        self.assertTrue(errors)
        self.assertNotIn(token, ' '.join(errors))
        local_path = '/' + 'home/' + 'example/private/file\n'
        self.assertTrue(policy.content_errors('docs/a.md', local_path.encode()))

    def test_binary_oversize_and_invalid_text_are_rejected(self):
        for data in (b'\x00', b'\xff', b'x' * (policy.MAX_BYTES + 1), b'no newline'):
            with self.subTest(length=len(data)):
                self.assertTrue(policy.content_errors('docs/a.md', data))
        self.assertEqual([], policy.content_errors('docs/a.md', b'Safe public text.\n'))

    def test_links_must_point_into_the_public_source_set(self):
        tracked = {'README.md', 'docs/ROADMAP.md'}
        self.assertEqual([], policy.link_errors('docs/ROADMAP.md',
                         '[Home](../README.md) [Section](#section)', tracked))
        self.assertTrue(policy.link_errors('README.md', '[Private](.local/notes.md)', tracked))
        self.assertTrue(policy.link_errors('README.md', '[Escape](../other.md)', tracked))


if __name__ == '__main__':
    unittest.main()
