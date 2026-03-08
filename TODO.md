# TODO

## Next
- Fix remaining sender name edge cases — a few chats still show group name or odd identifiers.
- Investigate reply detection — current reply links do not yet match real WhatsApp behaviour.
- Remove seconds from displayed timestamps — old CSV/HTML may still preserve them.
- Make URLs clickable — render links as proper HTML anchors.
- Render *bold* and _italic_ markup — support common WhatsApp text formatting.

## Soon
- Add reactions / emojis — investigate message metadata and how reactions are stored.
- Add search pages — e.g. `Felix.html`, `Älveskär.html`.
- Merge duplicate Alexander chats — treat multiple identifiers as one logical conversation.
- Improve conversation TOC styling — smaller and greyer dates/month rows.
- Add per-chat statistics — total message count, possibly file size.

## Later
- Add example export files to GitHub — possibly a synthetic / humorous sample chat.
- Improve index pages — consider table layout instead of uneven date text.
- Add photo references — link to media filename or show extraction command.