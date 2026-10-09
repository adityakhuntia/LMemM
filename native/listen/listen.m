// LMemM Listen - on-device speech to text for the ⌃⌥N note window.
//
// Lives in its own tiny app bundle ("LMemM Listen.app") because macOS only lets an
// app with its own microphone / speech usage strings use Apple's speech recognizer;
// a Python process can't. dictation.py builds it (clang, once) and starts it with
// `open`, so macOS treats it as its own app and asks for permission once.
//
//   listen --status <out-file>
//     writes {"mic": ..., "speech": ...} (macOS's words: authorized, denied, restricted,
//     notDetermined) and exits. Never asks. First-run setup polls this.
//   listen --authorize <out-file>
//     lets macOS ask for Speech Recognition, then Microphone, and writes the same answer.
//   listen <out-file>
//     writes the running transcript to <out-file> (rewritten on every update)
//     stops when <out-file>.stop appears, after 120 s, or on SIGTERM;
//     the last write before exiting is followed by <out-file>.done
//
// Recognition is strictly on-device. Unsupported Macs/locales use typed notes.

#import <Foundation/Foundation.h>
#import <Speech/Speech.h>
#import <AVFoundation/AVFoundation.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static NSString *outPath;
static NSString *latest = @"";
static volatile sig_atomic_t stopRequested = 0;

static BOOL cancelled(void) {
    return stopRequested || ![[NSFileManager defaultManager] fileExistsAtPath:[outPath stringByDeletingLastPathComponent]]
        || [[NSFileManager defaultManager] fileExistsAtPath:[outPath stringByAppendingString:@".stop"]];
}

static BOOL configureLocalRecognition(SFSpeechRecognizer *rec, SFSpeechAudioBufferRecognitionRequest *req) {
    if (!rec || !rec.supportsOnDeviceRecognition) return NO;
    req.requiresOnDeviceRecognition = YES;
    return YES;
}

static void writeText(NSString *text) {
    latest = text ?: @"";
    [latest writeToFile:outPath atomically:YES encoding:NSUTF8StringEncoding error:nil];
}

static void finish(int code) {
    writeText(latest);
    [@"" writeToFile:[outPath stringByAppendingString:@".done"] atomically:YES
            encoding:NSUTF8StringEncoding error:nil];
    exit(code);
}

static void fail(NSString *why) {
    [why writeToFile:[outPath stringByAppendingString:@".error"] atomically:YES
            encoding:NSUTF8StringEncoding error:nil];
    finish(1);
}

static void onTerm(int sig) { stopRequested = 1; }

static void waitForPermission(dispatch_semaphore_t semaphore) {
    NSDate *deadline = [NSDate dateWithTimeIntervalSinceNow:60];
    while (dispatch_semaphore_wait(semaphore, DISPATCH_TIME_NOW) != 0) {
        if (cancelled()) finish(0);
        if ([deadline timeIntervalSinceNow] <= 0) fail(@"Permission request timed out; type your note instead");
        [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.05]];
    }
    if (cancelled()) finish(0);
}

static NSString *speechWord(void) {
    switch ([SFSpeechRecognizer authorizationStatus]) {
        case SFSpeechRecognizerAuthorizationStatusAuthorized: return @"authorized";
        case SFSpeechRecognizerAuthorizationStatusDenied: return @"denied";
        case SFSpeechRecognizerAuthorizationStatusRestricted: return @"restricted";
        default: return @"notDetermined";
    }
}

static NSString *micWord(void) {
    switch ([AVCaptureDevice authorizationStatusForMediaType:AVMediaTypeAudio]) {
        case AVAuthorizationStatusAuthorized: return @"authorized";
        case AVAuthorizationStatusDenied: return @"denied";
        case AVAuthorizationStatusRestricted: return @"restricted";
        default: return @"notDetermined";
    }
}

static void writeAnswer(NSString *path) {
    NSDictionary *answer = @{@"mic": micWord(), @"speech": speechWord()};
    NSData *json = [NSJSONSerialization dataWithJSONObject:answer options:0 error:nil];
    [json writeToFile:path atomically:YES];
}

// waits for a permission prompt to be answered (up to 100 s) without blocking the run loop
static void waitFor(dispatch_semaphore_t semaphore) {
    NSDate *deadline = [NSDate dateWithTimeIntervalSinceNow:100];
    while (dispatch_semaphore_wait(semaphore, DISPATCH_TIME_NOW) != 0 && [deadline timeIntervalSinceNow] > 0)
        [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.05]];
}

// --status / --authorize: report (or ask for) the two permissions, then exit
static int permissionMode(const char *mode, NSString *path) {
    umask(0077);
    if (strcmp(mode, "--authorize") == 0) {
        if ([SFSpeechRecognizer authorizationStatus] == SFSpeechRecognizerAuthorizationStatusNotDetermined) {
            dispatch_semaphore_t s1 = dispatch_semaphore_create(0);
            [SFSpeechRecognizer requestAuthorization:^(SFSpeechRecognizerAuthorizationStatus st) { dispatch_semaphore_signal(s1); }];
            waitFor(s1);
        }
        if ([AVCaptureDevice authorizationStatusForMediaType:AVMediaTypeAudio] == AVAuthorizationStatusNotDetermined) {
            dispatch_semaphore_t s2 = dispatch_semaphore_create(0);
            [AVCaptureDevice requestAccessForMediaType:AVMediaTypeAudio completionHandler:^(BOOL ok) { dispatch_semaphore_signal(s2); }];
            waitFor(s2);
        }
    }
    writeAnswer(path);
    return 0;
}

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        if (argc >= 3 && (strcmp(argv[1], "--status") == 0 || strcmp(argv[1], "--authorize") == 0))
            return permissionMode(argv[1], [NSString stringWithUTF8String:argv[2]]);
        if (argc < 2) { fprintf(stderr, "usage: listen <out-file>\n"); return 2; }
        outPath = [NSString stringWithUTF8String:argv[1]];
        umask(0077);
        signal(SIGTERM, onTerm);
        if (cancelled()) return 0;
        [[NSString stringWithFormat:@"%d", getpid()] writeToFile:[outPath stringByAppendingString:@".pid"]
            atomically:YES encoding:NSUTF8StringEncoding error:nil];
        writeText(@"");

        // 1. permissions (asked once; macOS remembers)
        __block SFSpeechRecognizerAuthorizationStatus speech = SFSpeechRecognizerAuthorizationStatusNotDetermined;
        dispatch_semaphore_t s1 = dispatch_semaphore_create(0);
        [SFSpeechRecognizer requestAuthorization:^(SFSpeechRecognizerAuthorizationStatus st) {
            speech = st; dispatch_semaphore_signal(s1);
        }];
        waitForPermission(s1);
        if (speech != SFSpeechRecognizerAuthorizationStatusAuthorized)
            fail(@"Speech Recognition permission denied: System Settings > Privacy & Security > Speech Recognition > LMemM Listen");

        // Check local support before requesting microphone access. No server fallback.
        SFSpeechRecognizer *rec = [[SFSpeechRecognizer alloc] initWithLocale:[NSLocale currentLocale]];
        if (!rec || !rec.isAvailable || !rec.supportsOnDeviceRecognition)
            rec = [[SFSpeechRecognizer alloc] initWithLocale:[NSLocale localeWithLocaleIdentifier:@"en-US"]];
        if (!rec || !rec.isAvailable) fail(@"Local speech recognition unavailable; type your note instead");
        SFSpeechAudioBufferRecognitionRequest *req = [[SFSpeechAudioBufferRecognitionRequest alloc] init];
        if (!configureLocalRecognition(rec, req))
            fail(@"On-device speech recognition unsupported; type your note instead");
        req.shouldReportPartialResults = YES;
        if (@available(macOS 13.0, *)) req.addsPunctuation = YES;

        __block BOOL mic = NO;
        dispatch_semaphore_t s2 = dispatch_semaphore_create(0);
        [AVCaptureDevice requestAccessForMediaType:AVMediaTypeAudio completionHandler:^(BOOL ok) {
            mic = ok; dispatch_semaphore_signal(s2);
        }];
        waitForPermission(s2);
        if (!mic) fail(@"Microphone permission denied: System Settings > Privacy & Security > Microphone > LMemM Listen");

        // 3. microphone -> recognizer
        AVAudioEngine *engine = [[AVAudioEngine alloc] init];
        AVAudioInputNode *input = engine.inputNode;
        AVAudioFormat *fmt = [input outputFormatForBus:0];
        [input installTapOnBus:0 bufferSize:1024 format:fmt block:^(AVAudioPCMBuffer *buf, AVAudioTime *when) {
            [req appendAudioPCMBuffer:buf];
        }];
        [engine prepare];
        NSError *err = nil;
        if (![engine startAndReturnError:&err]) fail([NSString stringWithFormat:@"Couldn't start the microphone: %@", err.localizedDescription]);

        __block BOOL ended = NO;
        __block NSString *recognitionError = nil;
        [rec recognitionTaskWithRequest:req resultHandler:^(SFSpeechRecognitionResult *r, NSError *e) {
            if (r) writeText(r.bestTranscription.formattedString);
            if (e) recognitionError = e.localizedDescription;
            if (e || r.isFinal) ended = YES;
        }];

        // 4. run until asked to stop, then let the last words come through
        NSString *stopPath = [outPath stringByAppendingString:@".stop"];
        NSDate *deadline = [NSDate dateWithTimeIntervalSinceNow:120];
        while (!cancelled() && !ended && [deadline timeIntervalSinceNow] > 0
               && ![[NSFileManager defaultManager] fileExistsAtPath:stopPath]) {
            [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.05]];
        }
        [engine stop];
        [input removeTapOnBus:0];
        [req endAudio];
        NSDate *grace = [NSDate dateWithTimeIntervalSinceNow:1.5];
        while (!ended && [grace timeIntervalSinceNow] > 0)
            [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.05]];
        if (recognitionError && !cancelled()) fail(@"Local speech recognition failed; type your note instead");
        finish(0);
    }
    return 0;
}
