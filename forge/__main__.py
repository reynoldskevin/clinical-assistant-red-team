"""Package entrypoint so the app runs as ``python -m forge <args>``.

Railway's Nixpacks build does not reliably place the ``forge`` console script on
the runtime PATH, so the Procfile launches the dashboard via this module form.
Delegates to :func:`forge.run.main`.
"""

from forge.run import main

raise SystemExit(main())
