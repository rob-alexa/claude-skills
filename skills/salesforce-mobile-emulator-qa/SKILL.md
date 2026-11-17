---
name: salesforce-mobile-emulator-qa
description: "Seeing how a Salesforce screen really renders on a phone, through the Salesforce mobile app on an Android emulator. TRIGGER when: checking a mobile or phone layout, a QA step needs a phone view or screenshot, resizing a browser to a mobile viewport or setting a mobile user agent on a Salesforce page, a component that looks clipped or missing on mobile, creating or starting an Android emulator, installing or driving the Salesforce app on one, the app exiting on launch or its pages staying blank or stuck loading, or an AVD that will not boot. Not for a desktop capture (qa-handoff)."
metadata:
  version: "1.0"
  license: MIT
---

# salesforce-mobile-emulator-qa

How to get a real phone view of a Salesforce screen without a phone: the Salesforce mobile app on an
Android emulator, from creating the device through to a screenshot of the thing you are testing. It
exists because a browser cannot show you the mobile layout at all, and because nearly every step of
the emulator route fails in a way that looks like a different problem.

Point-in-time: the setup was measured on one Windows x86_64 machine during 2026, against Salesforce
sandboxes. The version numbers here (Android 16 system images `android-36` and `android-36.1`, and
Salesforce app builds 262.040.0 and 262.051.0) are the versions measured and will go stale. Verify
against your own machine, device, and org before asserting any of it as current fact.

Assumes Google's `android` command-line tool is installed; it wraps the SDK's `emulator` and `adb`,
and installing it is not covered here. The QA sub-task, desktop captures, and where a phone capture
sits in a handoff are `qa-handoff`. A rendering defect, once you can see it, is
`salesforce-flow-and-ui-defects`.

---

## Why an emulator rather than a resized browser

**Salesforce picks the form factor from the user agent, not the viewport.** A desktop browser resized
to 390px wide keeps `body.desktop`: the page stays the desktop page, and a flow modal clipped about
100px past the edge with no scrollbar, which reads as a mobile defect and is not one. Go the other
way and set a mobile user agent (Pixel with Chromium and iPhone with Safari alike), and the sandbox
measured redirected to Classic `home.jsp`, `/one/one.app` included.

You cannot separate the two in a browser, so no browser session, signed-in or headless, answers a
question about the phone layout. That is the whole reason for the emulator.

**A browser tool's mobile preset is the trap with a button on it.** The `mobile` preset of Claude
Code's in-app Browser `resize_window` tool emulates a mobile user agent and a 375px viewport together,
which is the redirect case, and it is the nearest thing to hand the moment somebody asks how a page
looks on a phone. A capture from it is not evidence about the phone layout either way.

Lightning App Builder's phone view (`qa-handoff`) names the components a phone will drop and needs no
emulator. Reach for the emulator when the question is how the page actually lays out and behaves in
the app.

---

## Creating and starting a device

Create by **profile**, not by a name you choose, because the AVD takes the profile's name.
`android emulator create --list-profiles` listed six: `small_phone`, `medium_phone`, `medium_tablet`,
`small_desktop`, `medium_desktop`, `large_desktop`. The first create for a profile pulls a system
image of about 1.9 GB.

```bash
android emulator create medium_phone
android emulator list
```

**Judge every `android` command by `android emulator list`, never by its exit code.**
`emulator create` printed *"Successfully created device"* and still exited 9.

**The very first run prints the Android SDK terms and then crashes** when the shell has no stdin to
accept them, which is the case in Claude Code's shell. It happens once: the acceptance is recorded,
and the second run works.

Start and stop the device through the CLI. Its help says `start` returns when the emulator is fully
started and ready rather than when the window appears; that is documented behavior and was not timed.
`--cold` skips the snapshot:

```bash
android emulator start --cold medium_phone
android emulator stop medium_phone
```

The raw `emulator` binary lives in the SDK at `%LOCALAPPDATA%\Android\Sdk\emulator\emulator.exe`.
`start` and `stop` cover the everyday job, so it does not need to be on PATH; reach for it by full
path for a flag the wrapper does not expose. `adb` (in the SDK's `platform-tools`) is worth putting on
PATH, because everything else here goes through it.

**A black screen right after launch is a WebView still painting, not a GPU fault.** A returned
`start` means the device booted, which is well before an app's login screen has drawn. In one session
an agent concluded GPU compositing was broken from a black framebuffer, stopped an emulator that had
already reached the Salesforce login screen, and had to start over. A `uiautomator` dump showing a
live `WebView` is evidence it is working. Check the state rather than reasoning about it:

```bash
adb exec-out screencap -p > captures/emulator.png
```

Write captures to a git-ignored folder rather than a bare filename at the repository root. A page
that stays blank once the app is signed in is a different problem: see **Blank pages or "Loading..."
in a signed-in app**.

**A cold boot can land on a secure lock screen, and then no app will launch.** Seen once:
`small_phone` came back from `-no-snapshot-load` asleep and locked, `screencap` returned black
throughout, and `monkey` answered `No activities found to run` for an app that `pm list packages`
still listed, which reads as the app having gone. Check the lock before anything else:

```bash
adb shell dumpsys window | grep isKeyguardShowing
adb shell dumpsys trust | grep deviceLocked
```

`KEYCODE_POWER` wakes the screen, but a swipe does not get past a PIN or pattern. The device
credential belongs to the person: hand the window over, and never have an agent enter it.

---

## Choosing the system image

### Use the x86_64 Play Store image, and do not go looking for an arm64 one

On a Windows x86_64 host the `android` CLI creates an x86_64 Google Play image by default, and that
is the image the Salesforce app ran on. The AVD's `config.ini` read:

```
image.sysdir.1=system-images/android-36.1/google_apis_playstore/x86_64/
abi.type=x86_64
PlayStore.enabled=true
```

The Play Store build of the app signed in to a sandbox on that kind of image once, rendering a record
page at 1080x2400, with `LoginHistory` carrying the matching `Salesforce for Android` /
`Salesforce 262` row. On later runs the Play Store build exited itself on launch, and Salesforce's
emulator build is what worked (**An app that exits itself on launch**). Calibration: the three
config lines were taken from `small_phone`, while the device on that first run was `medium_phone`,
whose config was later lost. Both came from the same `android emulator create` on the same host, and
the wrapper picks the host architecture, so the working device's architecture is a strong inference
rather than something taken off the device itself.

**So an app that exits moments after launch is not evidence of an architecture mismatch**, and an
arm64 image is a 1.9 GB download that cannot run on this host (**arm64 cannot run on an x86_64 host
at all**). One session took the Salesforce app exiting about 100 milliseconds after loading its
native library, with no login or security message, as proof that its native code cannot run on
x86_64, and was one step from pulling arm64. Take the `Process:` line out of `logcat` first, then
check **An app that exits itself on launch**.

### arm64 cannot run on an x86_64 host at all

Measured, so treat "try an arm64 image" as closed rather than untested. The image downloads and
extracts, the AVD accepts an `abi.type=arm64-v8a` config, and then the emulator refuses at boot:

```
FATAL | Avd's CPU Architecture 'arm64' is not supported by the QEMU2 emulator on x86_64 host.
        System image must match the host architecture.
```

What makes it look possible right up to that line is that `qemu-system-aarch64.exe` does ship, in
`%LOCALAPPDATA%\Android\Sdk\emulator\qemu\windows-x86_64\`, beside `armel`, `i386`, and `x86_64`.
The binary being present is not the front end being willing to use it. `emulator -accel-check`
reporting `WHPX ... is installed and usable` is about x86_64 guests and says nothing about arm64
either. And `system-images;android-36.1;google_apis_playstore;arm64-v8a` does exist in Google's
repository (1.96 GB), so confirming the image exists is not confirming it can run. The attempt cost a
2 GB download and 4.3 GB on disk before the FATAL line appeared.

### A partner's own mobile app might not install at all

A managed package's companion mobile app can refuse the emulator outright. Searching the Play Store
for one, on the same x86_64 image with a Google account signed in, returned an informational card
reading *"This app won't work for your device"*, with no install button. That is the vendor's
compatibility filter, not the emulator being broken: the Salesforce app installed from the Play Store
on the same image. Combined with the arm64 limit, such an app has no emulator route on a Windows
x86_64 host, and a real device is the only way to test it.

### Recovering when the `android` wrapper fails

Seen once: `android --version` itself failed with
`Error: LoadLibraryExW failed ... The specified module could not be found. (os error 126)` on every
subcommand, with `~/.android/cli` holding only `analytics/`, `bundles/`, `last_update_check`, and
`tos_displayed`, and no `cmdline-tools` (so no `sdkmanager`) anywhere in the SDK.

**You do not need the wrapper.** Both real tools work by full path and are enough for everything here:

```bash
"$LOCALAPPDATA/Android/Sdk/emulator/emulator.exe" -list-avds
"$LOCALAPPDATA/Android/Sdk/emulator/emulator.exe" -avd <name> -no-snapshot-load
"$LOCALAPPDATA/Android/Sdk/platform-tools/adb.exe" devices
```

An AVD can be created by hand when `avdmanager` is missing: copy a working `<name>.avd/config.ini`,
change `AvdId`, `abi.type`, `hw.cpu.arch`, and `image.sysdir.1`, and write a sibling `<name>.ini`
carrying `path`, `path.rel`, and `target`. `emulator -list-avds` picked it up immediately. A missing
`<name>.ini` beside a present `<name>.avd/` folder is exactly why an AVD vanishes from the list while
its disk images are still there.

---

## An app that exits itself on launch

**The fix is a different build of the app, not a different device: Salesforce's emulator build.**
The Play Store build 262.051.0 exited itself on `small_phone` (`EXIT_SELF`, `status=1`, about half a
second after launch, with the network up), while Salesforce's own emulator build 262.040.0 ran on the
same AVD, signed in to a sandbox, and rendered record pages (**Installing the Salesforce app**). Just
before exiting, the Play build reads `ro.debuggable`, `ro.secure`, `qemu.hw.mainkeys`,
`qemu.sf.lcd_density`, and SELinux `enforce`. That pattern looks like emulator or root detection,
but the log never says why the app exits, so treat the cause as an inference. Why the Play build ran
on the one earlier run was never established.

What the failing runs did establish, on two machines and on both `android-36` and `android-36.1`:

- The app's exit record (`adb shell dumpsys activity exit-info com.salesforce.chatter`) read
  `reason=1 (EXIT_SELF) subreason=0 status=1 trace=null`, so the app called `exit` on itself rather
  than being stopped by the system.
- A `nativeloader` line reported `lib/x86_64/libsalesforce_chatter.so` loading **ok**, so the loader
  was not rejecting the architecture.
- `Unexpected CPU variant for x86: x86_64` was logged shortly before each exit, but no log from the
  working run was kept, so that line cannot be taken as the cause.
- It was not the Play Store's first-run crash (the `Process:` line named the Salesforce app), and not
  stale app state (`pm clear com.salesforce.chatter` changed nothing).
- Rebuilding the AVD on a newer system image is not the fix: an `android-36` failure looked like the
  difference until an `android-36.1` AVD failed the same way.

**Record the app build on every run, working or failing, while the device still exists.**
`LoginHistory` keeps only the major version (`Browser = Salesforce 262`), so once a device is gone
the exact build that worked cannot be recovered:

```bash
adb shell dumpsys package com.salesforce.chatter | grep versionName
```

---

## Installing the Salesforce app

**Install Salesforce's emulator build, not the Play Store app.** Salesforce publishes a separate
Android build for emulators on its
[Mobile Debugging Tools](https://developer.salesforce.com/tools/mobile-debugging) page, and its
Trailhead unit
[Install Salesforce Mobile App Emulator for Android](https://trailhead.salesforce.com/content/learn/projects/set-up-your-salesforce-mobile-developer-tools-for-lightning-web-components/install-salesforce-mobile-app-emulator-for-android)
says to use it. When measured, the page's Android link,
`sfdc.co/salesforce-mobile-app-android-emulator`, resolved to
`SalesforceApp-Android-262.040.0#8-s1-externalDev.apk` under
`developer.salesforce.com/files/sfmobiletools/`, a file of 278,642,990 bytes. The server reports no
size, so expect a download of a few hundred MB. The page is drawn by JavaScript, so open it in a
browser: a plain fetch returns 403 or an empty shell, and the short link is a JavaScript redirect
that `curl -I` cannot follow. If an agent is fetching it, have it name the file, the source, and the
size when it asks to download.

**It has the same package name as the Play build, `com.salesforce.chatter`, and a lower version
code** (262040030 against the Play build's 262051001 when measured), so installing it over the Play
build fails with `INSTALL_FAILED_VERSION_DOWNGRADE`. Uninstall the Play build first:

```bash
adb uninstall com.salesforce.chatter
adb install <path-to-the>.apk
```

`android install` takes `--apks=<path>`, not a positional path.

**`INSTALL_FAILED_INSUFFICIENT_STORAGE` means Google's own app updates have filled the data
partition**, not that the APK is too big. `small_phone` had a 6 GB data partition, 84% full with
0.9 GB free. Raising `disk.dataPartition.size` in `config.ini` does not resize an existing AVD: a
`16G` setting still booted at 5.8 GB. Wiping the data would resize it, but it also removes the
Google sign-in. Without a wipe, roll back the updates to large Google apps the test does not use:

```bash
adb shell pm uninstall-system-updates com.google.android.youtube   # also Maps, Photos, Drive, Gmail, Chrome, the Google app
adb shell df -h /data
```

Rolling back 10 of those freed 1.5 GB. Leave WebView and Google Play services updated, because the
Salesforce app draws its pages in WebView. The Play Store installs the updates again over time.
`small_phone` also defaulted to `hw.ramSize=1024`; setting `4096` in `config.ini` took effect on the
next cold boot.

**On a fresh AVD the Play Store crashes on first open** with `FATAL EXCEPTION: LightweightExecutor`.
That crash is `com.android.vending`, the Play Store, not the Salesforce app, so check the `Process:`
line before attributing any crash on the device. The cause is stale first-run state, not a missing
Google account (`java.lang.IllegalArgumentException: Page with id WELCOME_PAGE not found in the last
session`). Clear it and reopen:

```bash
adb shell pm clear com.android.vending
```

---

## Signing in: hand the screen over

**Do not tap coordinates on the Salesforce login screen.** A tap aimed at **Use Custom Domain** once
submitted the remembered login instead and pushed an MFA approval to the tester's authenticator app.
Get the app to the login screen, then hand it to the person whose account it is and let them drive.
An agent never enters anyone's credentials or MFA.

### Moving the app to another org

**Clear the app's data; adding an account goes back to the old org.** The app signs in through a
Chrome Custom Tab opened at the last server it used. On 262.040.0, Profile menu >
**Change Account** > **Add new account** opened the previous org's own sign-in page in that tab, and
within a minute the app was back in that org, signed in, with nobody touching it (apparently the
browser's live single sign-on session, though that was not traced). The tab's **⋮** is Chrome's menu
and has no **Change Server**, and logging out did not reset it either: the next launch opened the
same sign-in tab again. This did:

```bash
adb shell pm clear com.salesforce.chatter
```

The app then opens on its license agreement (**I AGREE** / **I DECLINE**), which is the person's to
accept, and from there the person reached the other org's sign-in. Clearing also drops the org the
app was signed in to, and getting a System Administrator back in can cost a temporary verification
code (**A System Administrator's "Verify Your Identity"**), so check what the app holds before
clearing it.

**A passkey sheet can open on its own** (Google Play services, `FIDO_AUTHENTICATION` in `logcat`):
one opened while a sign-in tab was being closed, apparently from Salesforce's identity check. Cancel
it with `KEYCODE_BACK`, and never answer it.

### A System Administrator's "Verify Your Identity"

**A System Administrator can hit Salesforce's passkey challenge, "Verify Your Identity", after the
single sign-on succeeds.** In the org measured, Salesforce asked a privileged user for
phishing-resistant MFA and did not count the identity provider's authenticator-app approval as that.
A device-bound passkey, such as Windows Hello on a laptop, cannot be used on the emulator.
`VerificationHistory` showed the attempt as `Policy = TwoFactorAuthentication`,
`VerificationMethod = PwlessPasskey`, `Status = InProgress`.

A temporary verification code gets past it: in Setup, go to Users, click the user's name (not
**Edit**), then find **Temporary Verification Code** and click **Generate**. That needs **Manage MFA
in User Interface**, and a System Administrator can issue a code for their own user (measured once:
the org recorded `insertTwoFactorTempCode`, then a `TempCode` verification that `Succeeded`). The
person generates and enters the code themselves; an agent never handles it. Screenshots of that
screen come out black and `uiautomator` does not expose it, so ask the person what it says.

**Plan on that code for any org that wants a passkey, and query the right permission field.** One
developer sandbox refused every sign-in from the emulator, and from an iPhone, at
`Passwordless Login via Passkeys required` or `Multi-factor required`, while Chrome on the Windows
machine holding the passkey passed the same check seconds later. Manage MFA in User Interface is
`PermissionsDelegatedTwoFactor`; `PermissionsManageTwoFactor` is **Manage MFA in API**, and querying
that one reported nobody in the sandbox able to issue a code when the System Administrator profile
could. Check the person holds the right one before starting the emulator:

```bash
sf data query --query "SELECT COUNT() FROM PermissionSetAssignment WHERE AssigneeId = '<id>' AND PermissionSet.PermissionsDelegatedTwoFactor = true" --json | jq -r '.result.totalSize'
```

Whether a temporary code also gets past `Passwordless Login via Passkeys required` was not tried;
the code is verified only against **Verify Your Identity**.

### Confirming which org you reached

**Identify which org a single sign-on prompt belongs to from the Salesforce host or the custom domain
the app was pointed at, never from the account line the identity provider shows.** The identity
provider displays the person's plain federated address for every org, with no sandbox suffix, so a
missing suffix proves nothing. Taking it as proof of a production sign-in once led to telling a
tester not to approve a legitimate sandbox push.

**Confirm the org from `LoginHistory` afterwards rather than from the screen:**

```bash
sf data query --query "SELECT LoginTime, Application, Browser, LoginUrl, Status FROM LoginHistory WHERE UserId = '<id>' ORDER BY LoginTime DESC LIMIT 5" --json | jq -r '.result.records[] | "\(.LoginTime)  \(.Application)  \(.Browser)  \(.LoginUrl)  \(.Status)"'
```

`Application` reads `Salesforce for Android`, `Browser` carries the app's major version
(`Salesforce 262` in the runs measured), and `LoginUrl` names the org. Keep `Browser` in the query:
once a device is gone, that row is the only place the app version can still be found. `Application`
cannot be filtered on (`INVALID_FIELD ... can not be filtered in a query call`), so bound the query
by `UserId` and `LoginTime` and filter the rest in `jq`.

**A refused sign-in shows only here**, so check `Status` too, and do not filter for
`Salesforce for Android`: the emulator's refused attempt read `Application = Browser`,
`Browser = Salesforce 262`, and `Status = Passwordless Login via Passkeys required`, while the screen
itself could not be captured. A stray **Log In With a Passkey** card naming another org's host is
residue from an earlier mis-aimed tap, not the org you are in.

---

## Driving the app over adb

**In git-bash on Windows, remote paths need `MSYS_NO_PATHCONV=1`**, or `/sdcard/...` is rewritten
into a Windows path. That flag also breaks the local side of `adb pull`, so copy a file off the device
this way instead (`adb shell uiautomator dump` writes the window dump to `/sdcard/window_dump.xml`):

```bash
MSYS_NO_PATHCONV=1 adb exec-out cat /sdcard/window_dump.xml > captures/dump.xml
```

**`adb shell input text` cannot type a space**: use `%s`.

**The app's search overlay stays on top after a deep link resolves.** A poll that only looks for the
record page takes the overlay as a failed navigation. Send Back when an `AutoCompleteTextView` is
present:

```bash
adb shell input keyevent KEYCODE_BACK
```

### Lightning tap targets

**A Lightning radio button's accessibility node is a 6x8px hidden input at the label's top-left**
(`[78,1249][84,1257]` in one dump); the visible circle is drawn by the label and sits vertically
centered against it. Tapping the node's center misses, and so does tapping the label text. Aim at the
visible circle, located on a screenshot.

**`uiautomator`'s `checked` attribute is unreliable for Lightning radios**: it read `false` while the
radio was visibly selected. Judge selection from a screenshot crop, not from the attribute.

An Android **date picker** confirms with **SET**, beside **CLEAR** and **CANCEL**, not with an
on-page button.

---

## Blank pages or "Loading..." in a signed-in app

Symptom, seen on `medium_phone` with the emulator build 262.040.0 signed in to a sandbox: every page
the app draws in its WebView was blank, record pages and an app's home tab alike, or a record page
sat on "Loading...". The app's token refreshes were succeeding. `screencap` and
`adb emu screenrecord screenshot` showed the same blank page, so it was not a capture problem, and
`logcat` said only `Failed to fetch from network, falling back to cache`.

**These were all tried and left the pages blank, so do not spend a turn on them:** force-stop and
relaunch, two cold boots (`-no-snapshot-load`), deep links in both forms
(`https://<host>/lightning/r/...` and `salesforce1://sObject/<id>/view`), pull to refresh, and
`adb shell pm trim-caches 999G`. Whether a fresh sign-in clears it is unknown, because none was
tried; for a System Administrator it can cost a temporary verification code, so look inside the
WebView first.

### Look inside the WebView over its DevTools socket

The app's WebView listens on an abstract socket named `webview_devtools_remote_<pid>`, where `<pid>`
is the app's process id. The emulator build had one; whether the Play build does is not known. Find
it, forward a host port to it, and list the pages:

```bash
MSYS_NO_PATHCONV=1 adb shell grep -a webview_devtools_remote /proc/net/unix
adb shell pidof com.salesforce.chatter
adb forward tcp:9333 localabstract:webview_devtools_remote_<pid>
curl -s http://127.0.0.1:9333/json/list | jq -r '.[] | "\(.type)  \(.url)"'
```

The pid changes with every launch, so redo the forward after a force-stop or a reboot
(`adb forward --list` shows what is forwarded now; `adb forward --remove tcp:9333` drops it).

The `page` entry is the app's `bridge.app`, and its `url` is the thing to check. A healthy bridge is
`https://<host>/native/bridge.app?maxLayoutCacheSize=5&appContextId=<id>`. The broken one had a
second, URL-encoded copy of that address glued onto the end of `appContextId`:

```
https://<host>/native/bridge.app?maxLayoutCacheSize=5&appContextId=<id>/visualforce/session?url=https%3A%2F%2F<host>%2Fnative%2Fbridge.app%3FmaxLayoutCacheSize%3D5%26appContextId%3D<id>
```

At that address Aura boots from the app's cache and sends **no network requests at all**, so the
page container stays empty and nothing errors. [webview-cdp.mjs](webview-cdp.mjs), a small DevTools
client beside this file, shows it: `watch` logs every request, failure, console line, and navigation
for the seconds you give it, and on the broken bridge it logged the console start-up and not one
request. `eval` prints the value of an expression in the page. It needs Node 22 or later; run it from
this skill's folder or give its full path:

```bash
node webview-cdp.mjs watch 20
node webview-cdp.mjs eval 'location.href'
```

### The workaround, which does not last

Firing a record navigation inside the broken bridge makes the app reload it at the healthy address.
Single-quote the expression, or bash expands `$A` to nothing:

```bash
node webview-cdp.mjs watch 30 '$A.get("e.force:navigateToSObject").setParams({recordId:"<18-character Id>"}).fire(); "fired"'
```

The bridge reloaded at the plain address, ran `POST /services/auth/jwt/sidexchange` (200) and the
record calls (`RecordUi.getRecordWithFields`, `ActionBar.getActions`), and the record page rendered
on the emulator.

**It is not durable, and the root cause is unknown.** The next deep link, later the same day, put the
malformed address back and the record page sat on "Loading..." again. So run the workaround again
after each launch or deep link, and check the bridge address before counting a blank page as a
result. The blank pages followed a resume from the emulator's snapshot, which logged
`Failed to initialize aura ... BridgeCordovaUrlQueryParams` and destroyed-WebView warnings, so that
resume is the likeliest trigger. That is an inference: the aura error did not come back after the
cold boots, yet the address was still malformed after them.

### A field still missing: the app's cached layout

**The app keeps its own copy of each record page layout, and a stale copy hides a newly deployed
field.** Once the bridge rendered, a field deployed about two hours earlier was still missing from
the record's Details tab. The bridge's cookies carry one `flexipageLMT<PageApiName>` value per cached
page, an epoch in milliseconds:

```bash
node webview-cdp.mjs eval "document.cookie.split('; ').filter(c => c.startsWith('flexipageLMT')).join('\n')"
```

The page's value was five days older than the deploy. **A pull to refresh on the Details tab**
brought the field in, and afterwards the value was eight seconds later than the moment the deploy
created the field. That looks like the page's last-modified time as of the app's last fetch, an
inference from this one pair of values. On that interpretation, a value older than the deploy means
the app has not fetched the new layout, so pull to refresh on the tab that should show the change.
This is a different case from the related list in **Reading the result**, whose deploy was minutes
old when pull to refresh did not help.

---

## Reading the result

**After a deploy, the app kept showing the old page for about 10 minutes.** Force-stopping the app
and pulling down to refresh did not bring in a newly deployed related list any sooner, so an early
"it does not render" is not a finding. Once the deploy is older than that, check the app's cached
layout (**A field still missing: the app's cached layout**) before counting a missing component as a
defect.

**A record opened by deep link once showed no action bar at all**, while the same record showed all
four of its actions later, on the emulator and on an iPhone alike. So when a step expects an action
to be absent, the result counts only if the record's other actions are showing. An empty action bar
is not a pass.

For a layout question, the number that matters is horizontal overflow. Dump the window and compare
every labeled node's right edge against the screen width (1080 on `medium_phone`); anything past it
means the user has to scroll sideways.

For a text question, check the labeled nodes rather than screenshotting and eyeballing. **Use the
accessibility tree, never a DOM text walker.** The browser-side version of this trap cost three runs
and two browsers in one case, because a hidden `role="dialog"` reading "Sorry to interrupt / CSS
Error" sat on every Lightning page checked, and a walker that ignores visibility reports it as a
rendering failure.

---

## When the AVD will not boot

Symptom: `emulator -avd <name>` fails immediately, or `android emulator list` returns nothing while
the AVD folders are still on disk under `~\.android\avd\`.

The cause seen was that **Android Studio had been uninstalled**. That deletes `~\.android\cli`, the
`android` CLI's own installation, and sweeps through `~\.android` on the way, taking AVD config files
with it. There is no runtime coupling between Studio and the CLI, which is why the symptoms look
nothing like the cause: `java.lang.InternalError: Error loading java.security file` from a CLI that
worked an hour earlier, and an empty `android emulator list` while the AVD folders are still on disk.
Reinstall the CLI to recover it; the AVD has to be recreated.

Two things make that diagnosis harder than it should be. A truncated JRE (an eight-file
`~\.android\cli` with no `java.security`) is the uninstaller mid-flight, not a corrupt install. And
**`winget` printed *"Successfully uninstalled"* before the uninstaller finished**: 3,247 files were
still present immediately after, and none a minute later. Judge an uninstall by the file count a
minute on, never by the message. Both produced confident wrong conclusions in the same session.

Studio is not needed for any of this. The CLI is standalone: with Studio fully removed, it downloaded
its own JRE, pulled a 1.9 GB system image, and created a working AVD.

If only the config files are gone, the disk images survive. `userdata-qemu.img.qcow2` holds the
signed-in session and is worth keeping: rebuild `config.ini`, `<name>.ini`, and `hardware-qemu.ini`
against the existing images, or create a second profile and sign in once more.
