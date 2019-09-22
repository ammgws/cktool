# clubkatsudo scraper
Quick and dirty script to scrape attendance details from the clubkatsudo website.

Note: LINE notification feature requires LINE Business account and Imgur account.

```
Usage: clubkatsudo.py [OPTIONS]

Options:
  --set-password     Set password for clubkatsudo.com account. Will be base64
                     encoded and stored in config file
  --date [%Y%m%d]    YYYYMMDD of the event to scrape.
  --dryrun           Display final message but do not send.
  --config-dir PATH  Path to directory containing config file. Defaults to
                     $XDG_CONFIG_HOME/cktool.
  --cache-dir PATH   Path to directory to store logs and such. Defaults to
                     $XDG_CACHE_HOME/cktool.
  --help             Show this message and exit.
```

######Player information file
This file is...
