# SMS Gateway Remote WebSocket Protocol (Option A)

This server supports two modes:
- `local`: existing LAN HTTP mode (unchanged)
- `remote_ws`: Android app connects out to VPS via WebSocket

## Device WebSocket Endpoint

- URL: `/ws/sms-gateway/device`
- Full example: `wss://your-vps-domain/ws/sms-gateway/device`

## 1) Authenticate

Device must send `auth` first:

```json
{
  "type": "auth",
  "username": "gateway_user",
  "password": "gateway_pass",
  "device_id": "phone-01",
  "device_name": "Samsung A54",
  "platform": "android",
  "app_version": "1.2.0"
}
```

Server replies:

```json
{
  "type": "auth_ack",
  "success": true,
  "device_id": "phone-01",
  "message": "authenticated"
}
```

If credentials are wrong:

```json
{
  "type": "auth_ack",
  "success": false,
  "error": "invalid_credentials"
}
```

## 2) Keepalive

- Client can send text `ping`
- Server replies text `pong`

## 3) Command/Response Pattern

Server sends command:

```json
{
  "type": "command",
  "request_id": "uuid",
  "command": "health",
  "payload": {},
  "timestamp": "2026-04-11T10:00:00"
}
```

Device must reply:

```json
{
  "type": "response",
  "request_id": "same-uuid",
  "success": true,
  "data": {
    "status": "ok",
    "message": "Gateway online"
  }
}
```

Error reply:

```json
{
  "type": "response",
  "request_id": "same-uuid",
  "success": false,
  "error": "error message"
}
```

## Supported Commands

### `health`
- Payload: `{}`
- Expected `data` example:

```json
{
  "status": "ok",
  "message": "Gateway online",
  "device_info": {
    "battery": 83,
    "charging": false,
    "internet": true
  }
}
```

### `send_sms`
- Payload:

```json
{
  "message": "Noi dung SMS",
  "phoneNumbers": ["0912345678"],
  "simNumber": 1
}
```

- Expected `data` example:

```json
{
  "id": "message-id-or-uuid",
  "state": "processed",
  "deviceId": "phone-01"
}
```

### `message_status`
- Payload:

```json
{
  "message_id": "message-id-or-uuid"
}
```

- Expected `data` example:

```json
{
  "state": "sent",
  "error": null,
  "deviceId": "phone-01"
}
```

## HTTP API used by current frontend

No frontend transport change is required. FE still calls backend HTTP API:
- `GET /api/sms/config`
- `POST /api/sms/config`
- `GET /api/sms/health`
- `POST /api/sms/send`
- `GET /api/sms/ws/devices`

Backend will route to Local HTTP or Remote WS based on `connection_mode`.
