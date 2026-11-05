"""Embedded publication text is data; JavaScript is never evaluated."""
import json
import unittest

from dl_outcomes.page_payloads import embedded_page_text


class PagePayloadTests(unittest.TestCase):
    def test_nested_serialized_content_is_read_without_executing_code(self):
        payload = [json.dumps({'body': '<p>Our instructional model is 50/50.</p>'})]
        raw = '<script type="application/json">' + json.dumps(payload) + '</script>'
        self.assertEqual(embedded_page_text(raw), 'Our instructional model is 50/50.')

    def test_scripts_and_script_like_strings_are_not_publication_paragraphs(self):
        raw = '<script>raise Error("execute me")</script>'
        payload = json.dumps([
            'window.template = "<p>Wrong model 90/10</p>";',
            '<p>Published model 80/20<script>untrusted_code()</script></p>',
        ]).replace('</script>', '<\\/script>')
        raw += '<script type="application/json">' + payload + '</script>'
        self.assertEqual(embedded_page_text(raw), 'Published model 80/20')

    def test_repeated_html_is_deduplicated_and_malformed_payload_is_ignored(self):
        raw = '<script type="application/json">not JSON</script>'
        raw += '<script type="application/json">' + json.dumps([
            '<p>50% Spanish</p>', '<p>50% Spanish</p>', '<p>50% English</p>',
        ]) + '</script>'
        self.assertEqual(embedded_page_text(raw), '50% Spanish 50% English')
