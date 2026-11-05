import tempfile
import unittest
from pathlib import Path
from unittest import mock

from actions import video_player, youtube_video


class MediaPlayerTests(unittest.TestCase):
    def test_explicit_audio_request_starts_local_media_unmuted(self):
        with tempfile.TemporaryDirectory() as directory:
            media = Path(directory) / "song.mp3"
            media.touch()
            player = mock.Mock()

            result = video_player.video_player(
                {"action": "play", "source": str(media), "sound": True},
                player=player,
            )

        self.assertIn("mini-player", result)
        player.show_video.assert_called_once_with(
            str(media), media.name, muted=False,
        )

    def test_youtube_play_routes_through_the_embedded_media_player(self):
        player = mock.Mock()
        with mock.patch(
            "actions.video_player.video_player",
            return_value="status=opening source=lofi",
        ) as play_media:
            result = youtube_video._handle_play(
                {"query": "lofi music", "sound": True},
                player,
            )

        self.assertEqual(result, "status=opening source=lofi")
        play_media.assert_called_once_with(
            {
                "action": "play",
                "source": "lofi music",
                "sound": True,
            },
            player=player,
        )

    def test_failed_youtube_resolution_does_not_launch_another_app(self):
        player = mock.Mock()
        with mock.patch.object(
            video_player,
            "_resolve_youtube",
            return_value=("", "", "", "yt-dlp is unavailable"),
        ), mock.patch.object(video_player, "_still_wanted", return_value=True):
            video_player._play_youtube(player, "lofi music", 1, muted=False)

        player.show_video.assert_not_called()
        player.request_say.assert_called_once()
        self.assertIn("mini-player", player.request_say.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
