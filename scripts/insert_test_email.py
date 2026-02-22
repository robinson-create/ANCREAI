#!/usr/bin/env python
"""Insert a test email message for testing inbox display."""

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select

from app.database import async_session_maker
from app.models.mail import MailAccount, MailMessage


async def insert_test_email():
    async with async_session_maker() as db:
        # Get first connected mail account
        result = await db.execute(
            select(MailAccount).where(MailAccount.status == "connected").limit(1)
        )
        account = result.scalar_one_or_none()

        if not account:
            print("❌ No connected mail account found")
            print("Please connect a mail account first via the frontend")
            return

        print(f"✓ Using account: {account.email_address or account.provider}")

        # Create test email
        test_email = MailMessage(
            id=uuid4(),
            tenant_id=account.tenant_id,
            mail_account_id=account.id,
            provider_message_id=f"test_{uuid4()}",
            provider_thread_id=f"thread_{uuid4()}",
            internet_message_id=f"<test-{uuid4()}@example.com>",
            sender={"name": "Jean Dupont", "email": "jean.dupont@example.com"},
            to_recipients=[
                {"name": "", "email": account.email_address or "you@example.com"}
            ],
            subject="Test Email - Vérification affichage inbox",
            date=datetime.now(timezone.utc),
            snippet="Ceci est un email de test pour vérifier l'affichage dans la boîte de réception...",
            body_text="""Bonjour,

Ceci est un email de test pour vérifier que l'affichage de la boîte de réception fonctionne correctement.

Vous devriez voir cet email dans l'onglet "Boîte de réception" avec :
- L'expéditeur : Jean Dupont
- Le sujet : Test Email - Vérification affichage inbox
- Un aperçu du contenu

Vous pouvez cliquer dessus pour voir le détail complet et tester la fonction réponse.

Cordialement,
Jean Dupont""",
            body_html="""<p>Bonjour,</p>

<p>Ceci est un email de test pour vérifier que l'affichage de la boîte de réception fonctionne correctement.</p>

<p>Vous devriez voir cet email dans l'onglet <strong>"Boîte de réception"</strong> avec :</p>
<ul>
<li>L'expéditeur : Jean Dupont</li>
<li>Le sujet : Test Email - Vérification affichage inbox</li>
<li>Un aperçu du contenu</li>
</ul>

<p>Vous pouvez cliquer dessus pour voir le détail complet et tester la fonction réponse.</p>

<p>Cordialement,<br>Jean Dupont</p>""",
            is_read=False,
            is_sent=False,
            is_draft=False,
            has_attachments=False,
            is_indexed=False,  # Will be indexed on next sync cycle
            raw_headers={},
        )

        db.add(test_email)
        await db.commit()

        print(f"✓ Test email inserted: {test_email.id}")
        print(f"  Subject: {test_email.subject}")
        print(f"  From: {test_email.sender['name']} <{test_email.sender['email']}>")
        print(f"  Thread: {test_email.provider_thread_id}")
        print("\n🎯 Go to /app/email and check the 'Boîte de réception' tab!")
        print("   This email will be indexed into RAG on the next sync cycle (every 5min)")


if __name__ == "__main__":
    asyncio.run(insert_test_email())
