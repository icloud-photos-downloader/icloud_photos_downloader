"""Tests for the SummaryTracker class"""

from unittest.mock import patch, Mock
from icloudpd.summary import SummaryTracker
from icloudpd.logger import setup_logger


def test_prints_summary():
    """Test that the summary tracker prints the overall time"""
    with patch("time.time", side_effect=[1000.0, 1005.0]):
        logger = setup_logger()
        summary_tracker = SummaryTracker(logger)
        summary_tracker.start_timer()
        summary_tracker.stop_timer()

        mock_logger_info = Mock()
        with patch.object(logger, "info", mock_logger_info):
            summary_tracker.print_summary()

        assert mock_logger_info.call_args_list[0][0][0] == "\nExecution Summary"
        assert mock_logger_info.call_args_list[1][0][0] == "================="
        assert "Overall time:" in mock_logger_info.call_args_list[2][0][0]
        assert mock_logger_info.call_args_list[2][0][1].seconds == 5
