"""Telegram bot integration for icloudpd to handle sync commands"""

import datetime
import logging
import os
import threading
import time
from typing import Optional

import requests

from icloudpd.status import StatusExchange, Status


class TelegramBot:
    """Telegram bot to handle commands and trigger sync"""

    def __init__(
        self,
        logger: logging.Logger,
        token: str,
        chat_id: str,
        status_exchange: StatusExchange,
        polling_interval: int = 5,
        webhook_url: str | None = None,
    ) -> None:
        self.logger = logger
        self.token = token
        self.chat_id = chat_id
        self.status_exchange = status_exchange
        self.polling_interval = polling_interval
        self.webhook_url = webhook_url
        self.last_update_id = 0
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.thread = threading.Thread(target=self._poll_updates, daemon=True)
        self._waiting_for_auth_code = False  # Track if we're waiting for 6-digit code
        self._auth_requested = False  # Track if /auth command was sent

    def send_message(self, text: str) -> bool:
        """Send a message to the configured chat"""
        try:
            url = f"{self.base_url}/sendMessage"
            data = {"chat_id": self.chat_id, "text": text}
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            self.logger.error(f"Error sending Telegram message: {e}")
            return False

    def process_message(self, message: dict) -> None:
        """Process incoming Telegram message"""
        try:
            text = message.get("text", "").strip()
            if not text:
                return

            # Process /sync command
            if text == "/sync":
                self.logger.info("Telegram /sync command received, triggering sync (with cache)...")
                progress = self.status_exchange.get_progress()
                progress.resume = True
                progress.cancel = False
                self.status_exchange.set_force_full_sync(False)
                self.status_exchange.set_manual_sync(True)  # Mark as manual sync
                # Don't send message here - will be sent when sync starts with photo counts
            # Process /syncall command (full sync without cache)
            elif text == "/syncall":
                self.logger.info("Telegram /syncall command received, triggering full sync (no cache)...")
                progress = self.status_exchange.get_progress()
                progress.resume = True
                progress.cancel = False
                self.status_exchange.set_force_full_sync(True)
                self.status_exchange.set_manual_sync(True)  # Mark as manual sync
                # Don't send message here - will be sent when sync starts with photo counts
            # Process /stop command
            elif text == "/stop":
                self.logger.info("Telegram /stop command received, stopping current sync...")
                progress = self.status_exchange.get_progress()
                progress.cancel = True
                self.send_message("⏹️ Current synchronization stopped")
            # Process /status command
            elif text == "/status":
                self.logger.info("Telegram /status command received")
                status_message = self._get_status_message()
                self.logger.debug(f"Status message: {status_message}")
                if self.send_message(status_message):
                    self.logger.debug("Status message sent successfully")
                else:
                    self.logger.error("Failed to send status message")
            # Process /auth command - initiate authentication
            elif text == "/auth":
                self.logger.info("Telegram /auth command received, initiating authentication...")
                self._initiate_auth()
            # Legacy support: "Staticduo" command (case insensitive)
            elif text.lower() == "staticduo":
                self.logger.info("Telegram Staticduo command received, triggering sync...")
                self.status_exchange.get_progress().resume = True
                self.send_message("✅ Synchronization started")
            # Check if message is a 6-digit code (for MFA)
            elif self._is_six_digit_code(text) and self._waiting_for_auth_code:
                self.logger.info(f"Telegram 6-digit code received: {text}")
                self._handle_auth_code(text)
            # If waiting for auth code but received something else, remind user
            elif self._waiting_for_auth_code:
                self.send_message("❌ Please send a 6-digit code for authentication.")
        except Exception as e:
            self.logger.error(f"Error processing Telegram message: {e}")

    def _get_status_message(self) -> str:
        """Get current status message"""
        import time
        
        progress = self.status_exchange.get_progress()
        current_user = self.status_exchange.get_current_user()
        
        # Determine if downloading or idle
        # If there's a current user, we're processing (either downloading or filtering)
        is_processing = current_user is not None
        # Check if processing has actually started (processing_start_time > 0 means loop has started)
        has_started_processing = progress.processing_start_time > 0
        # Check if we're actually downloading (photos_count > 0 and counter < count)
        # If photos_checked > 0, we're processing photos (either filtering or downloading)
        # We're filtering if photos_checked > 0 (we're processing photos)
        # is_downloading should only be true if we're actually downloading NEW photos
        # For now, we'll show filtering progress whenever photos_checked > 0
        # and only show downloading if photos_counter is significantly less than photos_checked
        # (meaning we're downloading new photos, not just processing existing ones)
        is_filtering = (has_started_processing and
                       progress.photos_checked > 0 and 
                       progress.total_photos_in_icloud > 0)
        # Only show downloading if we have photos_count set and counter is progressing
        # But prioritize filtering if photos_checked is much larger than photos_counter
        is_downloading = (has_started_processing and
                         progress.photos_count > 0 and 
                         progress.photos_counter > 0 and
                         progress.photos_counter < progress.photos_count and
                         progress.photos_counter >= progress.photos_checked * 0.9)  # Only if counter is close to checked (downloading new photos)
        is_waiting = progress.waiting > 0
        
        if is_processing or is_filtering or is_downloading:
            # Show filtering progress if we're checking photos
            # Always show filtering if photos_checked > 0 (we're processing photos)
            # Only show downloading if we're actually downloading new photos (not just processing existing ones)
            if is_filtering:
                status_text = "🔄 Filtering photos"
                user_text = f"\n👤 User: {current_user}" if current_user else ""
                if progress.photos_checked > 0:
                    percent = round(100 * progress.photos_checked / progress.total_photos_in_icloud)
                    # Calculate rate if processing has started
                    rate_text = ""
                    if progress.processing_start_time > 0:
                        elapsed = time.time() - progress.processing_start_time
                        rate = progress.photos_checked / elapsed if elapsed > 0 else 0.0
                        rate_text = f" (Rate: {rate:.2f} items/s)"
                    progress_text = f"\n📊 Checked: {progress.photos_checked}/{progress.total_photos_in_icloud} ({percent}%){rate_text}"
                else:
                    # Processing just started, show initial message
                    progress_text = f"\n📊 Starting: 0/{progress.total_photos_in_icloud} (0%)"
                if progress.photos_to_download > 0:
                    progress_text += f"\n📥 {progress.photos_to_download} photos to download"
                return f"{status_text}{user_text}{progress_text}"
            elif is_downloading:
                # Actually downloading photos
                status_text = "🔄 Downloading"
                user_text = f"\n👤 User: {current_user}" if current_user else ""
                # Calculate rate if processing has started
                rate_text = ""
                if progress.processing_start_time > 0:
                    elapsed = time.time() - progress.processing_start_time
                    rate = progress.photos_counter / elapsed if elapsed > 0 else 0.0
                    rate_text = f" (Rate: {rate:.2f} items/s)"
                progress_text = (
                    f"\n📊 Progress: {progress.photos_counter}/{progress.photos_count} photos "
                    f"({progress.photos_percent}%){rate_text}"
                )
                if progress.photos_last_message:
                    progress_text += f"\n📝 {progress.photos_last_message}"
                return f"{status_text}{user_text}{progress_text}"
            else:
                # Processing but not filtering or downloading yet (authenticating, etc.)
                # If processing_start_time is set but photos_checked is 0, loop just started
                status_text = "🔄 Processing"
                user_text = f"\n👤 User: {current_user}" if current_user else ""
                if has_started_processing and progress.total_photos_in_icloud > 0:
                    # Loop has started, show initial progress
                    progress_text = f"\n📊 Starting processing of {progress.total_photos_in_icloud} photos..."
                    return f"{status_text}{user_text}{progress_text}"
                else:
                    return f"{status_text}{user_text}\n⏳ Preparing synchronization..."
        elif is_waiting:
            # Idle (waiting) status - in wait loop
            status_text = "⏸️ Idle (Waiting)"
            user_text = f"\n👤 User: {current_user}" if current_user else ""
            waiting_text = f"\n⏱️ Next synchronization in: {progress.waiting_readable}"
            return f"{status_text}{user_text}{waiting_text}"
        else:
            # Completely idle - calculate time until next sync
            status_text = "✅ Idle"
            user_text = f"\n👤 User: {current_user}" if current_user else ""
            
            # Calculate time until next sync if watch mode is active
            if progress.watch_interval > 0:
                current_time = time.time()
                if progress.last_sync_time > 0:
                    # Calculate based on last sync time
                    elapsed = current_time - progress.last_sync_time
                    remaining = progress.watch_interval - elapsed
                else:
                    # First sync hasn't happened yet, use full interval
                    remaining = progress.watch_interval
                
                if remaining > 0:
                    waiting_readable = str(datetime.timedelta(seconds=int(remaining)))
                    waiting_text = f"\n⏱️ Next synchronization in: {waiting_readable}"
                    return f"{status_text}{user_text}{waiting_text}"
                else:
                    # Should have started already, but show anyway
                    waiting_text = "\n⏱️ Next synchronization: Imminent"
                    return f"{status_text}{user_text}{waiting_text}"
            else:
                # No watch mode
                return f"{status_text}{user_text}\n💤 No activity at this time"

    def set_webhook(self, webhook_url: str) -> bool:
        """Set webhook URL for Telegram bot (push notifications instead of polling)"""
        try:
            url = f"{self.base_url}/setWebhook"
            data = {"url": webhook_url}
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            result = response.json()
            if result.get("ok"):
                self.logger.info(f"Webhook configured successfully: {webhook_url}")
                return True
            else:
                self.logger.error(f"Failed to set webhook: {result.get('description')}")
                return False
        except Exception as e:
            self.logger.error(f"Error setting webhook: {e}")
            return False

    def delete_webhook(self) -> bool:
        """Delete webhook and fall back to polling"""
        try:
            url = f"{self.base_url}/deleteWebhook"
            response = requests.post(url, timeout=10)
            response.raise_for_status()
            result = response.json()
            if result.get("ok"):
                self.logger.info("Webhook deleted, falling back to polling")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error deleting webhook: {e}")
            return False

    def start_polling(self) -> None:
        """Start the Telegram bot (webhook if available, otherwise polling)"""
        if self.webhook_url:
            if self.set_webhook(self.webhook_url):
                self.logger.info("Telegram bot using webhooks (push notifications)")
                return
            else:
                self.logger.warning("Failed to set webhook, falling back to polling")
        
        self.logger.info(f"Starting Telegram bot polling (interval: {self.polling_interval}s)...")
        self.thread.start()

    def _poll_updates(self) -> None:
        """Main polling loop for Telegram bot (uses long polling)"""
        while True:
            try:
                updates = self._get_updates()
                for update in updates:
                    self.process_update(update)
                # No sleep needed - long polling already waits for timeout_seconds
                # If we got updates, process immediately; if not, wait for next poll
            except Exception as e:
                self.logger.error(f"Error polling Telegram updates: {e}")
                # On error, wait a bit before retrying
                time.sleep(1)

    def _get_updates(self) -> list[dict]:
        """Get updates from Telegram using long polling"""
        url = f"{self.base_url}/getUpdates"
        # Use long polling with shorter timeout (1-2 seconds) for faster response
        # Telegram allows timeout up to 30 seconds, but shorter is better for responsiveness
        # We use min(2, polling_interval) to balance between responsiveness and API calls
        timeout_seconds = min(2, max(1, self.polling_interval // 3))
        params = {"timeout": timeout_seconds, "offset": self.last_update_id + 1}
        response = requests.get(url, params=params, timeout=timeout_seconds + 5)
        response.raise_for_status()
        updates = response.json().get("result", [])
        if updates:
            self.last_update_id = updates[-1]["update_id"]
        return updates

    def process_update(self, update: dict) -> None:
        """Process a Telegram update"""
        message = update.get("message")
        if message and str(message.get("chat", {}).get("id")) == self.chat_id:
            self.process_message(message)
        else:
            self.logger.debug(f"Ignoring message from unknown chat or without message: {update}")

    def send_progress_update(self) -> None:
        """Send progress update message (called periodically during download)"""
        progress = self.status_exchange.get_progress()
        if progress.photos_to_download > 0:
            message = f"📥 {progress.photos_counter}/{progress.photos_to_download}"
            self.send_message(message)

    def send_sync_start_message(self, photos_to_download: int, total_photos: int) -> None:
        """Send sync start message with photo counts"""
        message = f"Downloading: {photos_to_download} of {total_photos} total"
        self.send_message(message)

    def send_sync_complete_message(self, photos_downloaded: int, next_sync_seconds: int) -> None:
        """Send sync complete message"""
        next_sync_readable = str(datetime.timedelta(seconds=next_sync_seconds))
        message = f"Downloaded {photos_downloaded} photos. Next sync in {next_sync_readable}."
        self.send_message(message)

    def _is_six_digit_code(self, text: str) -> bool:
        """Check if text is a 6-digit code"""
        return len(text) == 6 and text.isdigit()

    def _initiate_auth(self) -> None:
        """Initiate authentication process"""
        # Force authentication by clearing cookies or triggering re-auth
        # The authentication will be handled in the main loop when it detects requires_2fa
        self.send_message("🔐 Starting authentication process...\n\nAuthentication will be attempted on the next synchronization. If a 6-digit code is required, I will ask for it here.")
        # Set resume flag to trigger sync, which will attempt authentication
        progress = self.status_exchange.get_progress()
        progress.resume = True
        progress.cancel = False
        # Set flag to force authentication (will be handled in base.py)
        self._auth_requested = True
        self._waiting_for_auth_code = False  # Reset flag, will be set when MFA is required

    def _handle_auth_code(self, code: str) -> None:
        """Handle 6-digit authentication code received via Telegram"""
        if self.status_exchange.get_status() == Status.NEED_MFA:
            if self.status_exchange.set_payload(code):
                self._waiting_for_auth_code = False
                self.send_message("✅ Code received, verifying...")
                self.logger.info(f"Authentication code provided via Telegram: {code}")
            else:
                self.send_message("❌ Error: Could not process the code. Please try again.")
                self.logger.error("Failed to set authentication code payload")
        else:
            self.send_message("❌ Error: No authentication code is expected at this time.")
            self.logger.warning(f"Received auth code but status is {self.status_exchange.get_status()}, not NEED_MFA")
            self._waiting_for_auth_code = False

    def request_auth_code(self, username: str) -> None:
        """Request authentication code via Telegram"""
        self._waiting_for_auth_code = True
        message = (
            f"🔐 Authentication required for {username}\n\n"
            f"Please send the 6-digit code that appears on your iPhone/iPad/Mac."
        )
        self.send_message(message)
        self.logger.info(f"Requested authentication code via Telegram for {username}")

    def notify_auth_required(self, username: str) -> None:
        """Notify that authentication is required (cookie expired or about to expire)"""
        message = (
            f"⚠️ Authentication required for {username}\n\n"
            f"The authentication cookie has expired or is about to expire.\n"
            f"Use the /auth command to renew authentication."
        )
        self.send_message(message)
        self.logger.info(f"Sent authentication required notification via Telegram for {username}")
