# MIT dining menus, side by side

`scrape.py` pulls each dining hall's menu from mit.cafebonappetit.com (today + tomorrow) into `site/data.json`.
`site/index.html` shows all halls side by side. A GitHub Action re-runs the scrape every morning and republishes the site.

Run locally: `pip install requests && python scrape.py && python -m http.server -d site`
