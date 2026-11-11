/* Synthetic microbenchmark for the poll-decimation compiler pass.
 * This measures only loop-check overhead; it is not a game benchmark. */
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
static uint64_t now_ns(void) {
    static LARGE_INTEGER frequency;
    LARGE_INTEGER counter;
    if (!frequency.QuadPart) QueryPerformanceFrequency(&frequency);
    QueryPerformanceCounter(&counter);
    return (uint64_t)((counter.QuadPart * 1000000000ull) / (uint64_t)frequency.QuadPart);
}
#else
#include <time.h>
static uint64_t now_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
}
#endif

#if defined(_MSC_VER)
#define NOINLINE __declspec(noinline)
#else
#define NOINLINE __attribute__((noinline))
#endif

static volatile uint32_t g_poll_flag = 0;
static volatile uint64_t g_sink = 0;
static uint64_t poll_calls = 0;

static NOINLINE void poll_handler(void) {
    ++poll_calls;
}

static NOINLINE uint64_t baseline(uint64_t iterations) {
    uint64_t x = 0x123456789abcdef0ull;
    for (uint64_t i = 0; i < iterations; ++i) {
        if (__atomic_load_n(&g_poll_flag, __ATOMIC_RELAXED)) {
            __atomic_store_n(&g_poll_flag, 0u, __ATOMIC_RELAXED);
            poll_handler();
        }
        x = x * 6364136223846793005ull + 1442695040888963407ull;
    }
    g_sink = x;
    return x;
}

#define DEFINE_DECIMATED(N) \
static NOINLINE uint64_t decimated_##N(uint64_t iterations) { \
    uint64_t x = 0x123456789abcdef0ull; \
    unsigned int budget = (N); \
    for (uint64_t i = 0; i < iterations; ++i) { \
        if (--budget == 0u) { \
            budget = (N); \
            if (__atomic_load_n(&g_poll_flag, __ATOMIC_RELAXED)) { \
                __atomic_store_n(&g_poll_flag, 0u, __ATOMIC_RELAXED); \
                poll_handler(); \
            } \
        } \
        x = x * 6364136223846793005ull + 1442695040888963407ull; \
    } \
    g_sink = x; \
    return x; \
}

DEFINE_DECIMATED(2)
DEFINE_DECIMATED(4)
DEFINE_DECIMATED(8)
DEFINE_DECIMATED(16)

typedef uint64_t (*bench_fn)(uint64_t);
static double run_once(bench_fn fn, uint64_t iterations, uint64_t *checksum) {
    const uint64_t start = now_ns();
    *checksum = fn(iterations);
    const uint64_t end = now_ns();
    return (double)(end - start) * 1000000.0 / (double)iterations;
}

static int compare_double(const void *a, const void *b) {
    const double x = *(const double *)a, y = *(const double *)b;
    return (x > y) - (x < y);
}

static void measure(const char *name, bench_fn fn, uint64_t iterations, unsigned int repeats) {
    double *times = (double *)calloc(repeats, sizeof(double));
    uint64_t checksum = 0;
    if (!times) return;
    poll_calls = 0;
    for (unsigned int i = 0; i < repeats; ++i)
        times[i] = run_once(fn, iterations, &checksum);
    qsort(times, repeats, sizeof(double), compare_double);
    printf("%-12s median=%9.2f ns/M iterations  min=%9.2f  checksum=%016" PRIx64 "  poll_calls=%" PRIu64 "\n",
           name, times[repeats / 2], times[0], checksum, (uint64_t)poll_calls);
    free(times);
}

int main(int argc, char **argv) {
    uint64_t iterations = 30000000ull;
    unsigned int repeats = 7;
    if (argc > 1) iterations = strtoull(argv[1], NULL, 10);
    if (argc > 2) repeats = (unsigned int)strtoul(argv[2], NULL, 10);
    if (iterations < 1000000ull || repeats < 3 || repeats > 31) {
        fprintf(stderr, "usage: %s [iterations>=1000000] [repeats=3..31]\n", argv[0]);
        return 2;
    }
    printf("Synthetic poll-check benchmark: iterations=%" PRIu64 ", repeats=%u, interrupt flag always clear\n",
           iterations, repeats);
    measure("baseline-1", baseline, iterations, repeats);
    measure("interval-2", decimated_2, iterations, repeats);
    measure("interval-4", decimated_4, iterations, repeats);
    measure("interval-8", decimated_8, iterations, repeats);
    measure("interval-16", decimated_16, iterations, repeats);
    return g_sink == 0 ? 1 : 0;
}
