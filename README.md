exosapient
==========

Install
-------

* `git clone`
* `git submodule update --init`
* `python deploy.py --flow --venv` and inspect the output, then pipe through sh to run
* create the file `src/exosapient/model/local.py` using the following template:

``` python
mbna_user = ''
mbna_pass = ''
mbna_security = {
    'Question?': 'Answer',
    'Question?': 'Answer',
    'Question?': 'Answer',
    }

bmo_number = ''
bmo_pass = ''
bmo_security = {
    'Question?': 'Answer',
    'Question?': 'Answer',
    'Question?': 'Answer',
    'Security question skipped': None,
    }
bmo_personal_phrase = ''
bmo_personal_image = ''  # Alt text of the personal image on the password page
```

Run
---

* `. bin/activate`
* `mbna [past_statements=1]`
* `bmo`
