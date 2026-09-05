# Dependency compatibility fix

Vercel's initial install failed because `@supabase/ssr@0.12.6` declares a peer dependency on `@supabase/supabase-js ^2.114.0`, while the app had pinned `@supabase/supabase-js` to `2.112.4`.

This branch updates `@supabase/supabase-js` to `2.114.0` so npm can resolve the dependency tree cleanly.
