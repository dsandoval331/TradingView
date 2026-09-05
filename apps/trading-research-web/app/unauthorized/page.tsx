export default function UnauthorizedPage() {
  return (
    <main className="authShell">
      <section className="authCard">
        <p className="eyebrow">ACCESS DENIED</p>
        <h1 className="authTitle">Account not authorized</h1>
        <p className="authCopy">Your Supabase identity is valid, but it is not on the Trading Research web allowlist.</p>
        <form action="/auth/signout" method="post"><button type="submit">Sign out</button></form>
      </section>
    </main>
  );
}
