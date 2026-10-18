LifeBoard runtime data lives here (app.db — auth, encrypted credentials, synced integration data).

This directory is bind-mounted into the container so data survives restarts/rebuilds.
Everything in it is gitignored except this file.
