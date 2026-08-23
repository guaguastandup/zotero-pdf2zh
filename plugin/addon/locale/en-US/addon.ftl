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
operation-error-partial-attachments = Imported only { $attached }/{ $total } attachment(s): { $message }
