"""Tests for the SummaryTracker class"""

from unittest.mock import patch, Mock
from icloudpd.summary import SummaryTracker


def test_prints_summary():
    """Test that the summary tracker prints the overall time"""
    with patch("time.time", side_effect=[1000.0, 1005.0]):
        summary_tracker = SummaryTracker()
        summary_tracker.start_timer()
        summary_tracker.stop_timer()

        mock_stdout = Mock()
        with patch("builtins.print", mock_stdout):
            summary_tracker.print_summary()

        assert mock_stdout.call_args_list[0][0][0] == "\nExecution Summary"
        assert mock_stdout.call_args_list[1][0][0] == "================="
        assert "Overall time: 0:00:05" in mock_stdout.call_args_list[2][0][0]