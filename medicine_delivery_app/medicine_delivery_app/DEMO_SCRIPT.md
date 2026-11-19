# Application demonstration

The steps below show the main clinic-to-messenger delivery process. Open two windows of the application so both account roles can be shown.

## Main demonstration

1. **Clinic login:** In Window A, sign in with username `clinic1` and PIN `1234`.
2. **Create a delivery:** Select **New delivery**, choose Sarah Tau, and enter the label `Monthly repeat`. Note the PIN displayed by the application.
3. **Messenger login:** In Window B, sign in with username `thabo` and PIN `1111`. Refresh the delivery list. The messenger should see the deliveries for Lekubu, without seeing the medicine name.
4. **Collect the parcel:** Select **Collect from clinic**.
5. **Confirm delivery:** Select **Confirm delivery**. Enter an incorrect PIN first to show the failed-attempt message, then enter the correct PIN.
6. **Check the clinic view:** Return to Window A and refresh. The delivery should show the **Delivered** status with the person and time recorded.

The demonstration shows how a delivery is created by the clinic, collected by a messenger and confirmed with a PIN.

## Additional demonstration: registration and messages

1. On the login screen, select **Create account** and register a new messenger. Enter **Lekubu** as the village.
2. Sign in to the clinic account (`clinic1` / `1234`). The new messenger should appear under **Waiting for approval**.
3. Select **Approve** for the new messenger.
4. Sign in using the new messenger account. Open **Messages**, write a message to the clinic and select **Also send by email**.
5. Return to the clinic account. Open **Messages** and check that the new message is shown as unread. The server window displays the email output when the console notification provider is in use.

## Screenshots for assessment

Capture the following screens:

- The clinic's new delivery and generated PIN.
- The messenger's delivery list.
- The delivery PIN confirmation screen.
- The clinic's delivery record after it has been marked Delivered.

## Demo accounts

| Account | Username | PIN |
|---|---|---|
| Clinic | `clinic1` | `1234` |
| Messenger | `thabo` | `1111` |

The existing messenger demo account is already approved. A newly registered messenger must be approved by the clinic before signing in.