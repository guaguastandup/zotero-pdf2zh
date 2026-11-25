startup-begin = Addon is loading
startup-finish = Addon is ready

prefs-title = PDF2zh

prefs-menu-translate = Translate PDF
prefs-menu-cut = Cut PDF
prefs-menu-crop-compare = Bilingual PDF(After Cropping)
prefs-menu-compare = Bilingual PDF

operation-progress-title = PDF2zh
operation-progress-processing = Preparing request...
operation-progress-submitting = Submitting “{ $fileName }”...
operation-progress-accepted = Submitted. { $action } “{ $fileName }” now
operation-progress-running = { $action } “{ $fileName }”{ $suffix }
operation-progress-importing = Server finished. Importing attachments for “{ $fileName }”...
operation-progress-file-done = Imported “{ $fileName }”
operation-progress-file-failed = “{ $fileName }” failed: { $message }
operation-progress-waiting = Waiting to process “{ $fileName }”
operation-progress-reconnecting = Rechecking the Server connection; the task may still be running
operation-progress-summary = Processing { $done }/{ $total } file(s)
operation-action-translate = Translating
operation-action-crop = Cropping
operation-action-compare = Building bilingual PDF
operation-action-crop-compare = Building cropped bilingual PDF
operation-batch-progress = { $current }/{ $total }: { $text }
operation-error-translate = “Translate PDF” only accepts an original PDF. Select the original attachment or its parent item.
operation-error-crop = This file cannot be cropped again. Select an original, mono, or dual attachment.
operation-error-compare = This file cannot be used for Bilingual Compare. Select an original or dual attachment.
operation-error-crop-compare = This file cannot be used for Cropped Bilingual Compare. Select an original, dual, or dual-cut attachment.
operation-error-crop-compare-terminal = This PDF is already a Cropped Bilingual Compare result. Select the original or a dual attachment instead.
operation-error-compare-terminal = This PDF is already a Bilingual Compare result. Select the original or a dual attachment instead.

operation-error-no-selection = Select an item or PDF attachment first.
operation-error-wenyi-translate-only = Wenyi supports Translate PDF only. Enable bilingual output in settings; cropping and separate comparison actions are not available.
operation-error-wenyi-key-required = Add and activate a DeepSeek configuration with a valid API key in LLM API Configuration.
operation-error-unknown = Unknown error
operation-error-prefix = Error: { $message }
operation-error-single-file = Failed to process { $fileName }: { $message }
operation-batch-started = Started { $count } file(s). Please wait.
operation-batch-completed =
    { $kind ->
        [failed] Failed. { $failed } file(s) failed
        [mixed] Finished. Succeeded: { $succeeded }, failed: { $failed }
       *[success] All done. Succeeded: { $succeeded }
    }
operation-error-no-files = The server did not return any files to import.
operation-error-completed-no-files = The task completed, but the Server returned no files.
operation-table-native-fallback = This Server does not support Prettier tables. Using native table translation for now; your setting stays enabled and takes effect automatically after a Server upgrade.
operation-error-partial-attachments = Imported only { $attached }/{ $total } attachment(s): { $message }
operation-reference-native-fallback = This Server does not support Reference Skip. Using native translation until the Server is updated.

local-service-start = Start local server
local-service-stop = Stop local server

server-error-missing-address-title = Set the PDF2zh Server address first
server-error-missing-address-help = Open Zotero Settings → PDF2zh. Enter the full address shown in the Server window in “Python Server IP”, for example http://localhost:8890, then click “Test Connection”.
server-error-invalid-address-title = The PDF2zh Server address is invalid
server-error-invalid-address-help = Open Zotero Settings → PDF2zh and check “Python Server IP”. Use an address with http:// or https://, a host and port, for example http://localhost:8890. Enter the PDF2zh Server address, not the model provider's API URL or a webpage URL with query parameters.
server-error-unreachable-title = Cannot connect to PDF2zh Server right now
server-error-unreachable-help =
    The Server may not be running, or the address or port may be incorrect.
    1. Start PDF2zh Server, wait until it is running, and keep its window open.
    2. Open Zotero Settings → PDF2zh and match “Python Server IP” to the address shown in the Server window.
    3. Click “Test Connection” and try again after it succeeds.
    For a Server on another computer, also check that computer's service and network connection.
server-error-timeout-title = The connection to PDF2zh Server timed out
server-error-timeout-help = The Server did not respond in time. Check that its window is still running and verify the address and port. For a remote Server, check the network too. Then use “Test Connection” in Zotero Settings → PDF2zh.
server-error-unexpected-response-title = The Server address or version may not match
server-error-unexpected-response-help = This address returned content the plugin could not recognize. Check that “Python Server IP” points to PDF2zh Server, not a model API or another website. If the address is correct, update the plugin and Server to matching versions.
server-error-access-denied-title = This address refused the connection request
server-error-access-denied-help = Check the PDF2zh Server address. For a remote or shared Server, check access permissions or contact the service provider.
server-error-file-too-large-title = The Server refused this file upload
server-error-file-too-large-help = The PDF may exceed the Server or proxy upload limit. Try a smaller PDF, or ask the remote service provider to check the upload limit.
server-error-file-missing-title = This result file was not found on the Server
server-error-file-missing-help = Check whether the task completed and whether its output files were moved or removed. If the result still exists on your computer, you can import it into Zotero manually.
server-error-http-title = The Server returned an error (HTTP { $status })
server-error-http-help = Check the error in the PDF2zh Server window. For a remote service, confirm it is available or share the technical details below with its maintainer.
server-error-phase-check = No files have been submitted for this operation. Try again after the connection works.
server-error-phase-submit = Submission could not be confirmed. After reconnecting, check the Server task list before submitting the same PDF again.
server-error-phase-poll = The task was submitted and may still be running. After reconnecting, check the task list before starting another translation.
server-error-phase-download = The translated files may already exist. Check the Server output files and import them after reconnecting before translating again.
server-error-details = Technical details (include these when reporting a problem): { $detail }

glossary-no-file = No glossary selected
glossary-picker = Choose a custom glossary CSV
glossary-error-format = Select a nonempty glossary CSV.
glossary-error-read = Could not read the glossary. Check that the UTF-8 file is still in the same location, or select it again in settings.
glossary-error-size = The glossary must be no larger than 1 MiB.
glossary-error-server = This PDF2zh Server does not support glossary uploads. Update the Server and try again, or remove the selected glossary in the plugin settings.

custom-service-server-required = This Server does not support custom service configurations. Update the Server and try again.
