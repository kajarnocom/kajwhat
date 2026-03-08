# WhatsApp CSV Schema

This document defines the first stable CSV schema used by `kajwhat.py`.

The purpose of the CSV file is to provide a readable, stable, intermediate
representation between:

```text
ChatStorage.sqlite -> WhatsApp.csv -> HTML conversations / indexes / search pages
```

## Design principles

- One row corresponds to one WhatsApp message.
- Message identifiers must be stable.
- The CSV must contain enough raw identifiers to allow future improvements
  without changing the schema too often.
- Some columns may initially be empty if the data is not yet fully decoded
  (for example `reactions`).

## Column specification

| CSV column | Source | Purpose |
|---|---|---|
| `message_id` | `ZWAMESSAGE.Z_PK` | Stable unique message identifier. Used as HTML anchor id. |
| `chat_id` | `ZWAMESSAGE.ZCHATSESSION` | Identifies the conversation / chat session. |
| `chatpartner` | `ZWACHATSESSION.ZPARTNERNAME` | Human-readable chat name. |
| `timestamp` | `ZWAMESSAGE.ZMESSAGEDATE` | Raw Apple timestamp. |
| `date` | derived from `timestamp` | Full datetime in readable form. |
| `year` | derived from `date` | Used for grouping. |
| `yyyymm` | derived from `date` | Used for grouping by month. |
| `dmydate` | derived from `date` | Used for daily headings in HTML. |
| `hhmm` | derived from `date` | Used for time display in HTML. |
| `from_jid` | `ZWAMESSAGE.ZFROMJID` | Raw sender JID. |
| `to_jid` | `ZWAMESSAGE.ZTOJID` | Raw recipient JID. |
| `from_name` | derived | Best human-readable sender name available. |
| `to_name` | derived | Best human-readable recipient name available. |
| `is_from_me` | `ZWAMESSAGE.ZISFROMME` | Whether the message was sent by me. |
| `text` | `ZWAMESSAGE.ZTEXT` | Message text. |
| `reply_to` | `ZWAMESSAGE.ZPARENTMESSAGE` | Points to the parent message if this message is a reply. |
| `group_member_id` | `ZWAMESSAGE.ZGROUPMEMBER` | Links message to a group member record where relevant. |
| `message_info_id` | `ZWAMESSAGE.ZMESSAGEINFO` | Reserved for future metadata / reaction support. |
| `reactions` | future decoding | Reserved for future reaction / emoji support. Initially may be empty. |
| `media_item_id` | `ZWAMESSAGE.ZMEDIAITEM` | Links message to media metadata where present. |
| `media_path` | `ZWAMEDIAITEM.ZMEDIALOCALPATH` | Local path of media item, if available. |
| `latitude` | `ZWAMEDIAITEM.ZLATITUDE` | Latitude for media with location metadata. |
| `longitude` | `ZWAMEDIAITEM.ZLONGITUDE` | Longitude for media with location metadata. |
| `message_type` | `ZWAMESSAGE.ZMESSAGETYPE` | Message type for future interpretation. |
| `group_event_type` | `ZWAMESSAGE.ZGROUPEVENTTYPE` | Group event type for future interpretation. |
| `push_name` | `ZWAMESSAGE.ZPUSHNAME` | Sender push name, potentially useful in group chats. |

## Notes on group chats

Group chats are expected to require special handling.

The most promising identifiers for proper sender resolution are:

- `ZWAMESSAGE.ZGROUPMEMBER`
- `ZWAGROUPMEMBER.Z_PK`
- `ZWAGROUPMEMBER.ZCONTACTNAME`
- `ZWAGROUPMEMBER.ZFIRSTNAME`
- `ZWAGROUPMEMBER.ZMEMBERJID`

The schema therefore includes both `group_member_id` and raw JIDs.

## Notes on reactions

Reaction / emoji support is intentionally reserved in the schema from the start,
even if the first implementation does not yet decode it.

The likely entry point is:

- `ZWAMESSAGE.ZMESSAGEINFO`
- `ZWAMESSAGEINFO.ZRECEIPTINFO`

## Notes on media

The first implementation should not extract media files themselves.

Instead, the CSV stores lightweight metadata:

- `media_item_id`
- `media_path`
- `latitude`
- `longitude`

This allows later tooling to locate or extract media without changing the CSV schema.

## Stability policy

This schema should be changed sparingly.

It is acceptable for some columns to remain empty in early versions if that helps
keep the schema stable while the extraction logic evolves.