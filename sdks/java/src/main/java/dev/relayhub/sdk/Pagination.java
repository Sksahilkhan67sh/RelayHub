package dev.relayhub.sdk;

import java.util.ArrayList;
import java.util.List;
import java.util.function.BiFunction;
import java.util.function.Consumer;

/**
 * RelayHub's list endpoints return a plain JSON array (no envelope, no cursor)
 * and take limit/offset parameters -- every {@code list(...)} method on every
 * resource already matches this shape, so it can be passed directly here.
 */
public final class Pagination {
    private Pagination() {}

    /**
     * Walks every page of a list endpoint, invoking {@code onItem} for each
     * result, until a page comes back shorter than {@code pageSize}:
     *
     * <pre>{@code
     * Pagination.paginate(50, job -> System.out.println(job.id),
     *     (limit, offset) -> client.getDlq().list(null, limit, offset));
     * }</pre>
     */
    public static <T> void paginate(int pageSize, Consumer<T> onItem, BiFunction<Integer, Integer, List<T>> fetchPage) {
        int offset = 0;
        while (true) {
            List<T> page = fetchPage.apply(pageSize, offset);
            for (T item : page) onItem.accept(item);
            if (page.size() < pageSize) return;
            offset += pageSize;
        }
    }

    /** Collects every page into a single list. Convenient for small result sets; prefer {@link #paginate} for large ones. */
    public static <T> List<T> collectAll(int pageSize, BiFunction<Integer, Integer, List<T>> fetchPage) {
        List<T> all = new ArrayList<>();
        paginate(pageSize, all::add, fetchPage);
        return all;
    }
}
