// Deterministic toy price-depth update benchmark. Not a full order book or gateway.
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <map>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

struct Update { int price; int delta; };
constexpr int kLevels = 4096;
constexpr int kBatch = 4096;
constexpr int kRuns = 120;

struct Dense {
    std::array<int, kLevels> levels{};
    int update(Update u) { return levels[u.price] += u.delta; }
};

struct Tree {
    std::map<int, int> levels;
    int update(Update u) { return levels[u.price] += u.delta; }
};

struct Result {
    std::uint64_t checksum;
    std::vector<double> samples;
};

template<class Container>
Result measure(const std::vector<Update>& updates) {
    using Clock = std::chrono::steady_clock;
    Container book;
    for (int p = 0; p < kLevels; ++p) {
        book.update({p, 1});
    }
    Result result{0, {}};
    result.samples.reserve(kRuns);
    for (int batch = 0; batch < kRuns; ++batch) {
        const auto started = Clock::now();
        for (int i = 0; i < kBatch; ++i) {
            result.checksum += book.update(updates[batch*kBatch+i]);
        }
        const auto elapsed = std::chrono::duration<double, std::nano>(Clock::now() - started);
        result.samples.push_back(elapsed.count() / kBatch);
    }
    std::sort(result.samples.begin(), result.samples.end());
    return result;
}

void print(const char* key, const Result& r) {
    std::cout << "\"" << key << "\":{\"p50_batch_ns_per_update\":"
              << r.samples[(kRuns*50+99)/100-1]
              << ",\"p99_batch_ns_per_update\":" << r.samples[(kRuns*99+99)/100-1]
              << ",\"checksum\":" << r.checksum << "}";
}

int main() {
    std::vector<Update> updates;
    updates.reserve(kBatch * kRuns);
    std::mt19937 rng(42);
    for (int i = 0; i < kBatch * kRuns; ++i) {
        auto value = rng();
        updates.push_back({static_cast<int>(value % kLevels), static_cast<int>((value >> 12) % 3 + 1)});
    }
    auto dense = measure<Dense>(updates);
    auto tree = measure<Tree>(updates);
    if (dense.checksum != tree.checksum) {
        throw std::runtime_error("Implementations disagree on the deterministic input");
    }
    std::cout << "{\"batch_count\":" << kRuns << ",\"updates_per_batch\":" << kBatch << ",";
    print("dense", dense);
    std::cout << ",";
    print("tree", tree);
    std::cout << "}\n";
}
