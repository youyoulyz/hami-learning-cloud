<!-- Copyright (C) 2025 Advanced Micro Devices, Inc. All rights reserved.  Portions of this notebook consist of AI-generated content. -->
<!--
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
-->


# files inside templates folder

* login.html: the login page, include notice.
* page.html: the base template for all html pages.
* resource_options_form.html: related to the resource option part on resource selection page.
* spawn.html: resource selection, time setup and spawn button.

# How to update notice displayed on the front page (Aborted).

1. Open login.html
2. Search for
```html
 <div class="w-full md:w-1/2 flex items-center justify-center p-6 md:p-16">
      </div>
```
3. The first line should indicate what is current mission
4. The following lines should indicate the introduction and basic purpose for this system.
5. Once you finish editing the webpage, you need to give it a new version like "v1.6", and edit the version in `build.sh` and `values.yaml` to susccessfully indicate the new version.
6. Run `helm_upgrade.sh` to upgrade whole system.

# How to update notice on frontpage without rebuild image
 ## Edit values.yaml and update helm ( Permanent )

1. Change values inside `value.yaml`
```
hub:
  extraFiles:
    announcement.txt:
      stringData: |
        Welcome to AUP Remote Lab!...
```

2. Do helm update, by run `scripts/helm_upgrade.bash`.
 ## Edit configmap with kubectl ( Not permanent )

 Run `kubectl edit configmap hub --namespace=jupyterhub ` to update its content.
