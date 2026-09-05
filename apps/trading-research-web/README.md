# Trading Research Web

Private Next.js frontend for the Trading Research Platform.

## V0.1 scope

- Deployable Next.js application shell
- Supabase browser/server clients using the publishable key
- Authentication boundary (next milestone)
- Protected, read-only database health check (next milestone)
- No service-role/secret key in browser code

## Vercel project settings

Set **Root Directory** to:

`apps/trading-research-web`

Add these environment variables in Vercel (Production, Preview, and Development as appropriate):

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`

Use the Supabase project URL and modern publishable key. Do not add a service-role/secret key to any `NEXT_PUBLIC_*` variable.

## Security gate

The first frontend database reads will use only tables that have RLS enabled. The four known Second1M tables with RLS disabled are excluded until the dedicated RLS review is completed.
