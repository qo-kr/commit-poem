from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from commitpoem.slack import SlackThreadError, post_publication


def response(data: dict) -> MagicMock:
    result = MagicMock()
    result.ok = True
    result.json.return_value = data
    return result


def test_image_is_first_block_and_notes_reply_to_exact_parent() -> None:
    with (
        patch("commitpoem.slack._upload_image", return_value="F123") as upload,
        patch("requests.post", side_effect=[response({"ok": True, "ts": "100.001"}),
                                            response({"ok": True, "ts": "100.002"})]) as post,
    ):
        ts = post_publication("token", "C123", "poem and quote", "person introductions", image=b"PNG", title="title")
    assert ts == "100.001"
    assert upload.call_args.args[1] is None  # private upload creates no extra channel message
    parent, reply = [call.kwargs["json"] for call in post.call_args_list]
    assert parent["blocks"][0] == {"type": "image", "slack_file": {"id": "F123"}, "alt_text": "title"}
    assert parent["blocks"][1]["text"]["text"] == "poem and quote"
    assert "thread_ts" not in parent
    assert reply["thread_ts"] == "100.001"
    assert reply["text"] == "person introductions"
    assert reply["unfurl_links"] is False


def test_text_only_still_has_notes_in_thread() -> None:
    with patch("requests.post", side_effect=[response({"ok": True, "ts": "100.001"}),
                                             response({"ok": True, "ts": "100.002"})]) as post:
        post_publication("token", "C123", "poem", "notes")
    assert all(block["type"] != "image" for block in post.call_args_list[0].kwargs["json"]["blocks"])
    assert post.call_args_list[1].kwargs["json"]["thread_ts"] == "100.001"


def test_reply_failure_identifies_already_posted_parent() -> None:
    with patch("requests.post", side_effect=[response({"ok": True, "ts": "100.001"}),
                                             response({"ok": False, "error": "ratelimited"})]) as post:
        with pytest.raises(SlackThreadError) as error:
            post_publication("token", "C123", "poem", "notes")
    assert error.value.parent_ts == "100.001"
    assert post.call_count == 2


def test_blocks_keep_long_parent_text_within_slack_limits() -> None:
    text = "a" * 3100 + "\n\n" + "b" * 2000
    with patch("requests.post", return_value=response({"ok": True, "ts": "100.001"})) as post:
        post_publication("token", "C123", text, "")
    blocks = post.call_args.kwargs["json"]["blocks"]
    assert all(len(block["text"]["text"]) <= 3000 for block in blocks)
    assert "".join(block["text"]["text"] for block in blocks).replace("\n", "") == text.replace("\n", "")


def test_short_paragraphs_are_packed_without_exceeding_block_count() -> None:
    text = "\n\n".join(["Note."] * 100)
    with patch("requests.post", return_value=response({"ok": True, "ts": "100.001"})) as post:
        post_publication("token", "C123", "poem", text)
    blocks = post.call_args.kwargs["json"]["blocks"]
    assert len(blocks) <= 50
    assert blocks[0]["text"]["text"] == text


def test_newly_uploaded_image_processing_is_retried_without_reuploading() -> None:
    pending = {"ok": False, "error": "invalid_blocks", "response_metadata": {
        "messages": ["[ERROR] invalid slack file [json-pointer:/blocks/0/slack_file.id/slack_file]"],
    }}
    with (
        patch("commitpoem.slack._upload_image", return_value="F123") as upload,
        patch("requests.post", side_effect=[response(pending), response(pending),
                                            response({"ok": True, "ts": "100.001"}),
                                            response({"ok": True, "ts": "100.002"})]) as post,
        patch("time.sleep") as sleep,
    ):
        assert post_publication("token", "C123", "poem", "notes", image=b"PNG") == "100.001"
    upload.assert_called_once()
    assert post.call_count == 4
    assert [call.args[0] for call in sleep.call_args_list] == [1, 2]


def test_other_slack_rejections_are_not_retried() -> None:
    from commitpoem.slack import SlackWebhookError
    with (
        patch("commitpoem.slack._upload_image", return_value="F123"),
        patch("requests.post", return_value=response({"ok": False, "error": "invalid_blocks"})) as post,
        patch("time.sleep") as sleep,
    ):
        with pytest.raises(SlackWebhookError):
            post_publication("token", "C123", "poem", "notes", image=b"PNG")
    post.assert_called_once()
    sleep.assert_not_called()


def test_real_upload_completion_does_not_create_a_second_channel_message() -> None:
    with (
        patch('requests.get', return_value=response({'ok': True, 'file_id': 'F123',
                                                     'upload_url': 'https://files.slack.com/upload/test'})),
        patch('requests.post', side_effect=[response({}), response({'ok': True}),
                                            response({'ok': True, 'ts': '100.001'}),
                                            response({'ok': True, 'ts': '100.002'})]) as post,
    ):
        post_publication('token', 'C123', 'poem', 'notes', image=b'PNG')
    complete = post.call_args_list[1].kwargs['json']
    assert 'channel_id' not in complete and 'initial_comment' not in complete
    assert complete['files'][0]['id'] == 'F123'
    assert post.call_args_list[2].kwargs['json']['blocks'][0]['slack_file']['id'] == 'F123'


def test_image_upload_failure_keeps_one_text_parent_and_notes() -> None:
    from commitpoem.slack import SlackWebhookError
    with (
        patch('commitpoem.slack._upload_image', side_effect=SlackWebhookError('upload failed')),
        patch('requests.post', side_effect=[response({'ok': True, 'ts': '100.001'}),
                                            response({'ok': True, 'ts': '100.002'})]) as post,
    ):
        post_publication('token', 'C123', 'poem', 'notes', image=b'PNG')
    assert post.call_count == 2
    assert post.call_args_list[0].kwargs['json']['blocks'][0]['type'] == 'section'
    assert post.call_args_list[1].kwargs['json']['thread_ts'] == '100.001'


def test_image_readiness_retries_are_bounded() -> None:
    from commitpoem.slack import SlackAPIError
    pending = {'ok': False, 'error': 'invalid_blocks', 'response_metadata': {
        'messages': ['invalid slack file [json-pointer:/blocks/0/slack_file.id/slack_file]'],
    }}
    with (
        patch('commitpoem.slack._upload_image', return_value='F123'),
        patch('requests.post', return_value=response(pending)) as post,
        patch('time.sleep') as sleep,
    ):
        with pytest.raises(SlackAPIError):
            post_publication('token', 'C123', 'poem', 'notes', image=b'PNG')
    assert post.call_count == 5
    assert [call.args[0] for call in sleep.call_args_list] == [1, 2, 4, 8]


def test_ambiguous_parent_network_timeout_is_not_retried() -> None:
    import requests
    from commitpoem.slack import SlackWebhookError
    with (
        patch('commitpoem.slack._upload_image', return_value='F123'),
        patch('requests.post', side_effect=requests.Timeout()) as post,
        patch('time.sleep') as sleep,
    ):
        with pytest.raises(SlackWebhookError):
            post_publication('token', 'C123', 'poem', 'notes', image=b'PNG')
    post.assert_called_once()
    sleep.assert_not_called()


def test_oversized_comment_is_rejected_before_parent_is_posted() -> None:
    from commitpoem.slack import SlackWebhookError
    with (
        patch('commitpoem.slack._upload_image') as upload,
        patch('requests.post') as post,
    ):
        with pytest.raises(SlackWebhookError, match='50-block'):
            post_publication('token', 'C123', 'poem', 'a' * 150001, image=b'PNG')
    upload.assert_not_called()
    post.assert_not_called()
