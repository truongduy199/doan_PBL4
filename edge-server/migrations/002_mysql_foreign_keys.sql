-- 002_mysql_foreign_keys.sql
-- Circular Foreign Keys between parking_slots, bookings, sessions, and gate_events.

ALTER TABLE parking_slots
    ADD CONSTRAINT fk_parking_slots_active_booking
    FOREIGN KEY (active_booking_id) REFERENCES bookings(booking_id);

ALTER TABLE parking_slots
    ADD CONSTRAINT fk_parking_slots_reserved_session
    FOREIGN KEY (reserved_session_id) REFERENCES sessions(session_id);

ALTER TABLE bookings
    ADD CONSTRAINT fk_bookings_checkin_event
    FOREIGN KEY (checkin_event_id) REFERENCES gate_events(event_id);
