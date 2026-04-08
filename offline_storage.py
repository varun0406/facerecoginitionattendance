"""
Offline Storage and Sync Module
Handles local storage of attendance records and delayed synchronization with PostgreSQL
"""

import json
import os
import threading
from datetime import datetime
from typing import List, Dict, Optional
import logging
from config import OFFLINE_CONFIG, FILE_PATHS
from database import Database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OfflineStorage:
    """Manages offline storage and synchronization of attendance records"""
    
    def __init__(self):
        self.queue_file = FILE_PATHS['offline_queue_file']
        self.sync_log_file = FILE_PATHS['sync_log']
        self.max_queue_size = OFFLINE_CONFIG['max_queue_size']
        self.lock = threading.Lock()
        
        # Create offline queue directory if it doesn't exist
        os.makedirs(os.path.dirname(self.queue_file), exist_ok=True)
        
        # Initialize queue file if it doesn't exist
        if not os.path.exists(self.queue_file):
            self._save_queue([])
    
    def _load_queue(self) -> List[Dict]:
        """Load pending records from local storage"""
        try:
            with open(self.queue_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    
    def _save_queue(self, queue: List[Dict]):
        """Save pending records to local storage"""
        try:
            with open(self.queue_file, 'w', encoding='utf-8') as f:
                json.dump(queue, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving queue: {e}")
    
    def add_record(self, record: Dict) -> bool:
        """
        Add attendance record to offline queue
        Returns True if added successfully, False if queue is full
        """
        with self.lock:
            queue = self._load_queue()
            
            # Check queue size
            if len(queue) >= self.max_queue_size:
                self._log_sync(f"Queue full! Max size: {self.max_queue_size}")
                return False
            
            # Add timestamp if not present
            if 'queued_at' not in record:
                record['queued_at'] = datetime.now().isoformat()
            
            queue.append(record)
            self._save_queue(queue)
            self._log_sync(f"Record queued: ID={record.get('user_id', 'N/A')}")
            return True
    
    def get_pending_count(self) -> int:
        """Get number of pending records"""
        with self.lock:
            queue = self._load_queue()
            return len(queue)
    
    def sync_to_database(self, batch_size: Optional[int] = None) -> Dict:
        """
        Synchronize pending records to PostgreSQL database
        Returns dict with sync results
        """
        if batch_size is None:
            batch_size = OFFLINE_CONFIG['batch_size']
        
        with self.lock:
            queue = self._load_queue()
            
            if not queue:
                return {'success': True, 'synced': 0, 'failed': 0, 'errors': []}
            
            # Get batch to sync
            batch = queue[:batch_size]
            remaining = queue[batch_size:]
            
            synced = 0
            failed = 0
            errors = []
            
            # Try to sync batch
            for record in batch:
                if self._sync_single_record(record):
                    synced += 1
                else:
                    failed += 1
                    errors.append(f"Failed to sync record ID: {record.get('user_id', 'N/A')}")
                    # Keep failed record in queue
                    remaining.insert(0, record)
            
            # Save remaining queue
            self._save_queue(remaining)
            
            result = {
                'success': failed == 0,
                'synced': synced,
                'failed': failed,
                'remaining': len(remaining),
                'errors': errors
            }
            
            self._log_sync(f"Sync completed: {synced} synced, {failed} failed, {len(remaining)} remaining")
            return result
    
    def _sync_single_record(self, record: Dict) -> bool:
        """Sync a single queued clock-in or clock-out to the database."""
        try:
            return Database.apply_queued_attendance(record)
        except Exception as e:
            logger.error(f"Error syncing record: {e}")
            return False
    
    def _log_sync(self, message: str):
        """Log sync operations"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.sync_log_file, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] {message}\n")
        except Exception as e:
            logger.error(f"Error logging: {e}")
    
    def check_connectivity(self) -> bool:
        """Check if database connection is available"""
        return Database.test_connection()
