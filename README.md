Django app for managing multiple mass-mailing lists with both plaintext as
well as HTML templates with rich text widget integration, images, and a smart
queueing system all right from the admin interface.

Status
======
We are currently using this package in several large to medium-scale production
environments, but it should be considered a permanent work in progress.

Documentation
=============
Extended documentation is available on [Read the Docs](http://django-newsletter.readthedocs.org/).

Translations
============
Strings have been fully translated into many languages, with many more on their way.
Contributions to translations are welcome through [Transifex](http://www.transifex.net/projects/p/django-newsletter/).

Compatibility
=============
Currently, django-newsletter officially supports Django 2.2.x LTS, 3.1.x, and 3.2.x, and Python 3.6 through 3.9.

Requirements
============
Please refer to the [requirements.txt](http://github.com/jazzband/django-newsletter/blob/master/requirements.txt)
for an updated list of required packages.

Tests
==========
Fairly extensive tests are available for internal frameworks, web
(un)subscription, and mail sending. Sending a newsletter to large groups of recipients
(+15k) has been confirmed to work in multiple production environments. Tests
for pull requests and the master branch are automatically run through
[GitHub Actions](https://github.com/jazzband/django-newsletter/actions).

Contributing
=============
Want to contribute? Great!
Please refer to the [issues](https://github.com/jazzband/django-newsletter/issues) on
GitHub and read [CONTRIBUTING.rst](https://github.com/jazzband/django-newsletter/blob/master/CONTRIBUTING.rst).

Feedback
========
If you find any bugs or have a feature request for django-newsletter, don't hesitate to
open up an issue on [GitHub](https://github.com/jazzband/django-newsletter/issues)
(but please make sure your issue hasn't been noticed before, finding duplicates is a
waste of time). When modifying or adding features to django-newsletter in a fork, be
sure to let me know what you're building and how you're building it. That way we can
coordinate whether, when, and how it will end up in the main fork and (eventually) an
official release.

License
=======
This application is released under the GNU Affero General Public License version 3.
