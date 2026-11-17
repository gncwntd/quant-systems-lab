/* SPDX-License-Identifier: Apache-2.0 */
#include "qsl/order_book.h"

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>

static void print_price(uint32_t price)
{
    printf("%" PRIu32 ".%02" PRIu32, price / 100u, price % 100u);
}

static void print_quote(const qsl_quote *quote)
{
    printf("  bid=");
    if (quote->has_bid) {
        print_price(quote->bid_price);
        printf(" x %" PRIu64, quote->bid_quantity);
    } else {
        printf("N/A");
    }
    printf("  ask=");
    if (quote->has_ask) {
        print_price(quote->ask_price);
        printf(" x %" PRIu64, quote->ask_quantity);
    } else {
        printf("N/A");
    }
    int64_t spread;
    if (qsl_quote_spread(quote, &spread)) {
        printf("  spread=%" PRId64 " integer units", spread);
    } else {
        printf("  spread=N/A");
    }
    printf("  orders=%zu\n", quote->active_orders);
}

int main(void)
{
    /* Project-authored synthetic events. Display scale: 100 units = 1.00. */
    const qsl_event events[] = {
        {QSL_ADD, 101, QSL_BUY, 10000, 10},
        {QSL_ADD, 102, QSL_BUY, 10000, 6},
        {QSL_ADD, 201, QSL_SELL, 10002, 8},
        {QSL_CANCEL, 101, 0, 0, 4},
        {QSL_EXECUTE, 201, 0, 0, 3},
        {QSL_DELETE, 102, 0, 0, 0},
        {QSL_ADD, 103, QSL_BUY, 9998, 7},
        {QSL_DELETE, 101, 0, 0, 0}
    };
    const char *names[] = {"INVALID", "ADD", "CANCEL", "EXECUTE", "DELETE"};
    qsl_book book;
    qsl_book_init(&book);
    puts("Synthetic book demo: prices use scale 100; not market data.");
    for (size_t i = 0; i < sizeof(events) / sizeof(events[0]); ++i) {
        qsl_status status = qsl_book_apply(&book, &events[i]);
        if (status != QSL_OK) {
            fprintf(stderr, "Event %zu rejected with status %d\n", i + 1, (int)status);
            return EXIT_FAILURE;
        }
        qsl_quote quote;
        if (qsl_book_quote(&book, &quote) != QSL_OK) {
            return EXIT_FAILURE;
        }
        printf("%zu. %s id=%" PRIu64, i + 1, names[events[i].type], events[i].id);
        print_quote(&quote);
    }
    return EXIT_SUCCESS;
}
