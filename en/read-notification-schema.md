# Read Marker, Inbox, Notification Schema

Read markers are actor-private state. Notifications are derived projections, not canonical truth.

Objects:

- `read_marker`
- `receipt`
- `notification`

Multi-device merge chooses the causally latest marker, with HLC and device id as tie-breakers.
