import { login } from "./actions";

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  const params = await searchParams;
  return (
    <main className="authShell">
      <section className="authCard">
        <p className="eyebrow">TRADING RESEARCH PLATFORM</p>
        <h1 className="authTitle">Private research access</h1>
        <p className="authCopy">Sign in with an authorized Supabase account. Public signup is not enabled.</p>
        {params.error && <p className="authError">Sign-in failed. Check your email and password.</p>}
        <form className="authForm" action={login}>
          <label htmlFor="email">Email</label>
          <input id="email" name="email" type="email" autoComplete="email" required />
          <label htmlFor="password">Password</label>
          <input id="password" name="password" type="password" autoComplete="current-password" required />
          <button type="submit">Sign in</button>
        </form>
      </section>
    </main>
  );
}
