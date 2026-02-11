-- Fix RLS policy for notifications
-- Allow authenticated users to insert notifications (backend uses anon key)

DROP POLICY IF EXISTS "System can insert notifications" ON notifications;

-- Backend can create notifications for any user
CREATE POLICY "Backend can insert notifications"
  ON notifications FOR INSERT
  WITH CHECK (true);

-- Alternative: Only allow inserts for authenticated users
-- CREATE POLICY "Authenticated can insert notifications"
--   ON notifications FOR INSERT
--   TO authenticated
--   WITH CHECK (true);
