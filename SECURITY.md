# Security

## Historical credentials

Several preserved local snapshots contained literal Gemini API keys. Treat those keys as compromised and rotate them before reuse.

The restored source reads only `GEMINI_API_KEY` from the environment. It never stores or logs that value.

## Authority

LLM output is untrusted narrative. It cannot deny an explicit exit, grant God Mode, route a player, authorize changes to another player's world, or classify a person permanently.

## Privacy

The local `data/` folder contains player state, chronicle entries and dreams. It is ignored by Git and must not be published without the player's consent.
