#include <algorithm>
#include <cerrno>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <random>
#include <stdexcept>
#include <string>
#include <string_view>
#include <sys/stat.h>
#include <time.h>
#include <vector>

namespace {

struct Options {
    std::size_t n = 0;
    std::size_t t = 0;
    std::size_t repetitions = 30;
    std::size_t warmup = 5;
    std::uint64_t seed = 42;
    std::string csv_path;
    bool append = false;
    bool self_test = false;
    bool quiet = false;
    bool timer_probe = false;
    std::size_t timer_samples = 100000;
    std::size_t batch = 1;
    std::size_t order_position = 1;
    std::size_t repetition_offset = 0;
};

[[noreturn]] void fail(const std::string& message) {
    throw std::runtime_error(message);
}

std::uint64_t parse_u64(std::string_view text, const char* name) {
    if (text.empty()) fail(std::string("empty value for ") + name);
    std::size_t pos = 0;
    unsigned long long value = 0;
    try {
        value = std::stoull(std::string(text), &pos, 10);
    } catch (const std::exception&) {
        fail(std::string("invalid integer for ") + name + ": " + std::string(text));
    }
    if (pos != text.size()) fail(std::string("invalid integer for ") + name + ": " + std::string(text));
    return static_cast<std::uint64_t>(value);
}

void usage(const char* argv0) {
    std::cerr
        << "Usage: " << argv0 << " --n N --t T [options]\n"
        << "Options:\n"
        << "  --repetitions R   measured repetitions (default: 30)\n"
        << "  --warmup W        unmeasured warm-up runs (default: 5)\n"
        << "  --seed S          deterministic PRNG seed (default: 42)\n"
        << "  --csv PATH        write raw measurements to CSV\n"
        << "  --append           append to CSV (header written only if needed)\n"
        << "  --quiet            suppress human-readable summary\n"
        << "  --batch B          experimental block identifier (default: 1)\n"
        << "  --order-position P position of T inside the block (default: 1)\n"
        << "  --repetition-offset K  add K to repetition numbering (default: 0)\n"
        << "  --self-test        run deterministic correctness tests and exit\n"
        << "  --timer-probe      characterize CLOCK_MONOTONIC_RAW and exit\n"
        << "  --timer-samples K  samples for --timer-probe (default: 100000)\n";
}

Options parse_args(int argc, char** argv) {
    Options o;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        auto require_value = [&](const char* option) -> std::string_view {
            if (i + 1 >= argc) fail(std::string("missing value after ") + option);
            return argv[++i];
        };
        if (arg == "--n") o.n = parse_u64(require_value("--n"), "N");
        else if (arg == "--t") o.t = parse_u64(require_value("--t"), "T");
        else if (arg == "--repetitions") o.repetitions = parse_u64(require_value("--repetitions"), "repetitions");
        else if (arg == "--warmup") o.warmup = parse_u64(require_value("--warmup"), "warmup");
        else if (arg == "--seed") o.seed = parse_u64(require_value("--seed"), "seed");
        else if (arg == "--csv") o.csv_path = std::string(require_value("--csv"));
        else if (arg == "--append") o.append = true;
        else if (arg == "--quiet") o.quiet = true;
        else if (arg == "--batch") o.batch = parse_u64(require_value("--batch"), "batch");
        else if (arg == "--order-position") o.order_position = parse_u64(require_value("--order-position"), "order-position");
        else if (arg == "--repetition-offset") o.repetition_offset = parse_u64(require_value("--repetition-offset"), "repetition-offset");
        else if (arg == "--self-test") o.self_test = true;
        else if (arg == "--timer-probe") o.timer_probe = true;
        else if (arg == "--timer-samples") o.timer_samples = parse_u64(require_value("--timer-samples"), "timer-samples");
        else if (arg == "--help" || arg == "-h") { usage(argv[0]); std::exit(EXIT_SUCCESS); }
        else fail("unknown option: " + arg);
    }
    return o;
}

std::uint64_t monotonic_raw_ns() {
    timespec ts{};
    if (clock_gettime(CLOCK_MONOTONIC_RAW, &ts) != 0) {
        fail(std::string("clock_gettime(CLOCK_MONOTONIC_RAW) failed: ") + std::strerror(errno));
    }
    return static_cast<std::uint64_t>(ts.tv_sec) * 1'000'000'000ULL
         + static_cast<std::uint64_t>(ts.tv_nsec);
}

#if defined(__GNUC__) || defined(__clang__)
__attribute__((noinline))
#endif
void squared_distances(const double* q,
                       const double* x,
                       double* distances,
                       std::size_t n,
                       std::size_t t) noexcept {
    for (std::size_t i = 0; i < n; ++i) {
        const double* row = x + i * t;
        double sum = 0.0;
        for (std::size_t j = 0; j < t; ++j) {
            const double d = q[j] - row[j];
            sum += d * d;
        }
        distances[i] = sum;
    }
}

double checksum(const std::vector<double>& values) {
    long double acc = 0.0L;
    for (double v : values) acc += static_cast<long double>(v);
    return static_cast<double>(acc);
}

void fill_data(std::vector<double>& q,
               std::vector<double>& x,
               std::vector<double>& distances,
               std::uint64_t seed) {
    std::mt19937_64 rng(seed);
    std::uniform_real_distribution<double> dist(-1.0, 1.0);
    for (double& v : q) v = dist(rng);
    for (double& v : x) v = dist(rng);
    std::fill(distances.begin(), distances.end(), 0.0);
}

void run_timer_probe(std::size_t samples) {
    if (samples == 0) fail("timer-samples must be greater than zero");

    timespec res{};
    if (clock_getres(CLOCK_MONOTONIC_RAW, &res) != 0) {
        fail(std::string("clock_getres(CLOCK_MONOTONIC_RAW) failed: ") + std::strerror(errno));
    }
    const std::uint64_t resolution_ns =
        static_cast<std::uint64_t>(res.tv_sec) * 1'000'000'000ULL +
        static_cast<std::uint64_t>(res.tv_nsec);

    std::vector<std::uint64_t> deltas;
    deltas.reserve(samples);
    for (std::size_t i = 0; i < samples; ++i) {
        const std::uint64_t a = monotonic_raw_ns();
        const std::uint64_t b = monotonic_raw_ns();
        deltas.push_back(b - a);
    }
    std::sort(deltas.begin(), deltas.end());
    const std::uint64_t median = deltas[deltas.size() / 2];
    const std::size_t p95_index = static_cast<std::size_t>(
        std::ceil(0.95 * static_cast<double>(deltas.size())) - 1.0);
    const std::uint64_t p95 = deltas[std::min(p95_index, deltas.size() - 1)];
    std::uint64_t min_positive = 0;
    for (const auto d : deltas) {
        if (d > 0) { min_positive = d; break; }
    }

    std::cout << "TIMER_PROBE"
              << " samples=" << samples
              << " clock_resolution_ns=" << resolution_ns
              << " min_positive_delta_ns=" << min_positive
              << " median_pair_delta_ns=" << median
              << " p95_pair_delta_ns=" << p95
              << '\n';
}

void run_self_test() {
    {
        const std::vector<double> q{1.0, 2.0};
        const std::vector<double> x{1.0, 2.0, 2.0, 4.0};
        std::vector<double> out(2, -1.0);
        squared_distances(q.data(), x.data(), out.data(), 2, 2);
        if (std::abs(out[0] - 0.0) > 1e-12 || std::abs(out[1] - 5.0) > 1e-12) {
            fail("self-test 1 failed");
        }
    }
    {
        const std::vector<double> q{-1.0, 0.5, 3.0};
        const std::vector<double> x{-1.0, 0.5, 3.0};
        std::vector<double> out(1, -1.0);
        squared_distances(q.data(), x.data(), out.data(), 1, 3);
        if (std::abs(out[0]) > 1e-12) fail("self-test 2 failed");
    }
    std::cout << "SELF_TEST_OK\n";
}

bool file_exists_and_nonempty(const std::string& path) {
    struct stat st{};
    return ::stat(path.c_str(), &st) == 0 && st.st_size > 0;
}

void write_csv(const Options& o,
               const std::vector<std::uint64_t>& elapsed_ns,
               double final_checksum) {
    if (o.csv_path.empty()) return;

    const bool had_content = o.append && file_exists_and_nonempty(o.csv_path);
    std::ios::openmode mode = std::ios::out;
    mode |= o.append ? std::ios::app : std::ios::trunc;
    std::ofstream out(o.csv_path, mode);
    if (!out) fail("cannot open CSV output: " + o.csv_path);

    if (!had_content) {
        out << "N,T,batch,order_position,repetition,elapsed_ns,seed,checksum\n";
    }
    out << std::setprecision(17);
    for (std::size_t r = 0; r < elapsed_ns.size(); ++r) {
        out << o.n << ',' << o.t << ',' << o.batch << ',' << o.order_position << ','
            << (o.repetition_offset + r + 1) << ',' << elapsed_ns[r] << ','
            << o.seed << ',' << final_checksum << '\n';
    }
}

} 

int main(int argc, char** argv) {
    try {
        const Options o = parse_args(argc, argv);
        if (o.self_test) {
            run_self_test();
            return EXIT_SUCCESS;
        }
        if (o.timer_probe) {
            run_timer_probe(o.timer_samples);
            return EXIT_SUCCESS;
        }
        if (o.n == 0) fail("N must be greater than zero");
        if (o.t == 0) fail("T must be greater than zero");
        if (o.repetitions == 0) fail("repetitions must be greater than zero");
        if (o.n > std::numeric_limits<std::size_t>::max() / o.t) fail("N*T overflows size_t");
        
        std::vector<double> q(o.t);
        std::vector<double> x(o.n * o.t);
        std::vector<double> distances(o.n);
        fill_data(q, x, distances, o.seed);

        volatile double warmup_sink = 0.0;
        for (std::size_t w = 0; w < o.warmup; ++w) {
            squared_distances(q.data(), x.data(), distances.data(), o.n, o.t);            
            warmup_sink = warmup_sink + distances[w % o.n];
        }
        (void)warmup_sink;

        std::vector<std::uint64_t> elapsed;
        elapsed.reserve(o.repetitions);
        volatile double measured_sink = 0.0;

        for (std::size_t r = 0; r < o.repetitions; ++r) {
            const std::uint64_t start = monotonic_raw_ns();
            squared_distances(q.data(), x.data(), distances.data(), o.n, o.t);
            const std::uint64_t end = monotonic_raw_ns();
            elapsed.push_back(end - start);            
            measured_sink = measured_sink + distances[r % o.n];
        }
        (void)measured_sink;
        
        const double final_checksum = checksum(distances);
        if (!std::isfinite(final_checksum)) fail("non-finite checksum; numerical result is invalid");

        write_csv(o, elapsed, final_checksum);

        if (!o.quiet) {
            std::vector<std::uint64_t> sorted = elapsed;
            std::sort(sorted.begin(), sorted.end());
            const auto median = sorted[sorted.size() / 2];
            std::cout << "N=" << o.n
                      << " T=" << o.t
                      << " repetitions=" << o.repetitions
                      << " median_ns=" << median
                      << " checksum=" << std::setprecision(17) << final_checksum
                      << '\n';
        }
        return EXIT_SUCCESS;
    } catch (const std::exception& e) {
        std::cerr << "ERROR: " << e.what() << '\n';
        return EXIT_FAILURE;
    }
}
