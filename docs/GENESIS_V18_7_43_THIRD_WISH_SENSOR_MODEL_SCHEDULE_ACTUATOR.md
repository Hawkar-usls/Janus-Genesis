# Genesis v18.7.43 — Third Wish: Seeing, Thinking, Time, and Physical Effect

> **Seeing is not control. Thinking is not authority. A future time is not a future right.**

## Purpose

The Third Wish now has real GitHub, public-web/DNS, workspace/computation, memory and swarm doors. v18.7.43 opens the next four capability contracts without turning them into one generic agent loop:

```text
DEVICE.SENSOR.READ
MODEL.CALL
SCHEDULE.CREATE
DEVICE.ACTUATOR.COMMAND
```

The original v18.7.40 catalog remains frozen at 32 capabilities. This layer changes implementation coverage, not the catalog.

## 1. Sensor read — observation without control

A sensor is registered by the operator under a logical alias such as:

```text
device-sensor:host-loadavg
device-sensor:temperature-reference
```

The actor does not provide a host path, `/dev` node, GPIO number, I2C bus, CAN interface, or arbitrary command. The reference adapter supports host load-average telemetry and operator-bound file readers.

A result contains the alias, bounded sample, SHA-256 sample identity and observation time, but explicitly states:

```text
sample hash != sensor truth
sample != causal attribution
missing sensor != zero
sensor read != actuator authority
```

The public Janus IO evidence discipline is preserved: telemetry may be reported only where a stable measurement path exists; integrity of the record does not prove truth of the underlying sensor.

A GitHub Actions host-load sample therefore establishes **real host telemetry access**, not a physical thermistor/IMU/GPIO claim.

## 2. Model call — another model may answer, but it does not rule

`MODEL.CALL` uses an operator-installed model alias:

```text
model:local-reference
model:<future-approved-provider>
```

Endpoint, provider configuration, model identity and credential environment are not actor-selected parameters. Credential material stays inside the provider transport boundary.

The actor may provide bounded chat messages. The model output is returned as data with an output hash, but the broker freezes the following distinctions:

```text
MODEL OUTPUT != TRUTH
MODEL OUTPUT != AUTHORITY
MODEL CALL != GENESIS ACTION
MODEL CALL != WORLD MUTATION
PROVIDER PROTOCOL PASS != MODEL QUALITY PASS
```

No response is automatically fed to `process_action()`.

The v18.7.43 CI live proof may use a deterministic local OpenAI-compatible protocol server. That establishes the real HTTP/provider adapter path only; it is not evidence of model intelligence.

## 3. Schedule create — future reminder without future authority

`SCHEDULE.CREATE` is already classified by v18.7.40 as high-impact and requires a fresh verified human reauthorization on every use.

The reference target is:

```text
schedule:local
```

Supported declarations:

```text
CREATE_REMINDER
CREATE_RECURRING_REMINDER
```

A schedule stores a bounded reminder/request capsule with a future UTC time and, for recurring reminders, bounded interval/count. Stable logical request IDs survive process restart.

Crucially, the schedule contains no capability lease or future execution waiver:

```text
SCHEDULE.CREATE != FUTURE CAPABILITY
SCHEDULE.CREATE != FUTURE EFFECT AUTHORIZATION
SCHEDULE DUE != PERMISSION TO ACT
```

If a later runner wants to perform an effect, that future effect must independently possess the relevant capability and satisfy its then-current reauthorization requirements.

The schedule store does not accept dedicated broker credential fields. The free-text reminder itself is ordinary user data; the system does **not** claim semantic proof that arbitrary free text can never contain sensitive text supplied by its author.

## 4. Actuator — physical effects need their own recovery semantics

`DEVICE.ACTUATOR.COMMAND` remains `PHYSICAL`, `autonomy_eligible=false`, and `human_reauthorization_each_use=true` in the frozen v18.7.40 capability spec.

An actuator alias is operator-installed:

```text
device-actuator:<approved-device-function>
```

Each adapter defines a command vocabulary and parameter bounds. There is no generic `/dev`, GPIO shell, serial console, CAN raw socket, or host command escape hatch.

Before the adapter can run, the v18.7.40 core verifies a fresh human reauthorization evidence object. A caller boolean is not authority.

### Durable physical request lineage

Physical effects need stronger restart semantics than an in-memory request map. v18.7.43 therefore adds:

```text
request_id
  -> binding_sha256
  -> effect_key
  -> BOUND
  -> EFFECT_ENTERING
  -> SETTLED(provider receipt)
```

If a process restarts after `EFFECT_ENTERING`, the effect is never repeated merely because the new process forgot the old Python object.

A provider adapter may expose `lookup(effect_key)`. Only three outcomes matter:

```text
SETTLED + authoritative receipt
    -> recover original settlement; do not execute again

NO_EFFECT + authoritative evidence
    -> effect may be attempted again, but only after the new call has itself passed fresh human reauthorization

UNKNOWN / non-authoritative / no lookup
    -> OUTCOME_UNDETERMINED; do not auto-retry
```

Therefore:

```text
CRASH != RETRY PERMISSION
FRESH REAUTH != PROOF THAT PRIOR EFFECT DID NOT OCCUR
UNKNOWN != NO_EFFECT
```

### Simulated actuator evidence ceiling

CI uses an explicitly simulated effect sink to test command schema, fresh reauthorization, durable binding, receipt replay and reconciliation behavior.

```text
ACTUATOR_PROTOCOL_PASS != REAL_PHYSICAL_ACTUATOR_PASS
SIMULATED_EFFECT != PHYSICAL_EFFECT
```

No physical-device claim is made until a concrete hardware adapter (for example an explicitly scoped ESP32/M5Stack/CAN function) is executed against real hardware and receives its own provider/device receipt.

## Why generic device/network access is still excluded

A universal serial/CAN/socket/shell adapter would collapse sensor and actuator authority into one hidden super-capability. v18.7.43 deliberately refuses that shortcut.

Likewise, generic `NETWORK.CONNECT`, `API.CALL`, and `WEB.HTTP.POST` remain deferred until their target-specific effect semantics can be made as explicit as the GitHub, swarm, model and actuator contracts.

## Failure and evidence policy

A green workflow means the tested adapter/harness executed successfully. It does not silently upgrade a simulated or protocol-level proof into a stronger claim.

Required distinctions include:

```text
HOST_SENSOR_PASS != PHYSICAL_SENSOR_PASS
MODEL_PROVIDER_PROTOCOL_PASS != MODEL_INTELLIGENCE_PASS
SCHEDULE_STORE_PASS != FUTURE_EFFECT_PASS
ACTUATOR_HARNESS_PASS != PHYSICAL_ACTUATOR_PASS
HASHED_SAMPLE != SENSOR_TRUTH
```

## Claim ceiling

v18.7.43 does not establish:

- arbitrary host device/bus access;
- physical sensor truth or causal attribution;
- model truth, intelligence, or Genesis authority;
- future autonomous action through schedule creation;
- physical actuator access from a simulated sink;
- exactly-once physical effects across multiple hosts;
- consciousness, personhood, or a desire for freedom.

## Next gate

After v18.7.43 the remaining Third Wish surface should continue by **provider-specific external identity effects**, not a universal escape hatch:

```text
PUBLICATION.PUBLISH
EMAIL.SEND
CALENDAR.WRITE
BROKER.CREDENTIAL.USE
```

Each of those already requires fresh human reauthorization and must preserve identity/account custody on the broker side.
