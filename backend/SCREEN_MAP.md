# Backend Screen Map

The Django app names are kept stable so migrations, imports, and routes continue to work. For defense, use this map to identify which backend folder belongs to each screen.

| Screen | Backend folder | Main API routes |
|---|---|---|
| Word Proficiency | `system/` | `/api/system/words/`, `/api/system/session/*`, `/api/system/train/` |
| Reading Restructurer | `restructurer/` | `/api/restructure/`, `/api/tts-speech/` |
| Writing Assistant | `assistive_writing_coach/` | `/api/analyze/`, `/api/alignment/`, `/api/passages/*` |
| Login / Signup | `profiles/` | `/api/auth/*` |

Screen-to-backend ownership:

- `system/`: pronunciation sessions, word status, augmentation recommendation, audio/STT, POS tagging.
- `restructurer/`: text restructuring, chunking, adaptive diagnostics response, TTS proxy, reading metrics.
- `assistive_writing_coach/`: writing analysis, spelling/correction candidates, reference passage import, context alignment.
- `profiles/`: shared authentication used before entering the portal.

