import unittest
from unittest import mock

from plugins import color_protocol


class ColorProtocolTests(unittest.TestCase):
    def test_plugin_declaration_is_well_formed(self):
        self.assertEqual(color_protocol.PLUGIN["name"], "color_protocol")
        self.assertEqual(
            color_protocol.PLUGIN["parameters"]["required"],
            ["color"],
        )

    def test_known_color_updates_the_app_live(self):
        player = mock.Mock()

        result = color_protocol.run({"color": "blue"}, player=player)

        player.set_ui_color.assert_called_once_with("#4287ff")
        self.assertIn("Blue protocol activated", result)

    def test_unknown_color_does_not_change_the_app(self):
        player = mock.Mock()

        result = color_protocol.run({"color": "ultraviolet"}, player=player)

        player.set_ui_color.assert_not_called()
        self.assertIn("color protocol is not available", result)

    def test_missing_display_returns_error(self):
        result = color_protocol.run({"color": "red"})

        self.assertIn("display is unavailable", result)


if __name__ == "__main__":
    unittest.main()
