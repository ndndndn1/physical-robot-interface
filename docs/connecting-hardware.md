# Connecting physical equipment

This release targets deterministic mock products. A real robot connects by replacing
the mock `RobotPort`; consumers do not change their request or response models.

## Product record required before connection

Record the equipment's product classification, manufacturer, exact product/model name,
controller and firmware revisions, supported capabilities, joint count, payload and
speed limits, coordinate frames, vendor protocol, and safety manual revision. Do not
claim conformance from a family name alone.

## Interface and connection procedure

1. Place the controller and gateway on an isolated OT Ethernet segment. Do not publish
   the RobotPort directly to the internet. Allow only the controller, gateway, time
   source, and explicitly required monitoring destinations.
2. For ROS 2, use a dedicated domain ID and robot namespace. Map navigation to the
   product's pose/action interface and manipulation to its joint trajectory action.
   Map joint state, pose, controller health, and the safety input back to `RobotState`.
3. Implement bounded deadlines, watchdogs, reconnect backoff, monotonic local timing,
   command ID persistence, and state-version compare-and-set at the adapter boundary.
4. Wire the physical E-stop and safety controller exactly as the manufacturer requires.
   Read their status independently. Never translate a network `protective_stop` into a
   claim that the hardware E-stop circuit has engaged.
5. Run schema and read-only conformance first. Run command conformance only on an
   isolated test robot inside a guarded area. Then run vendor commissioning, HIL,
   payload, limit, loss-of-network, restart, and safety validation.
6. Enable production traffic only after the named safety owner approves the documented
   risk assessment and rollback procedure.

The adapter must preserve idempotency across restarts and reject unsupported commands
before sending anything to hardware. A vendor fault must become a stable failed command
record; it must not be retried invisibly when motion could be duplicated.
