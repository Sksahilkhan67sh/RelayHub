package relayhub

// FetchPageFunc fetches one page of results at the given limit/offset. Every
// RelayHub list endpoint returns a plain JSON array (no envelope, no cursor)
// with limit/offset query params -- this is the shape every List method already
// matches, so it can be passed directly to Paginate.
type FetchPageFunc[T any] func(limit, offset int) ([]T, error)

// Paginate walks every page of a list endpoint via callback, stopping once a
// page comes back shorter than pageSize:
//
//	err := relayhub.Paginate(50, func(item relayhub.DeadLetterJob) error {
//	    fmt.Println(item.ID)
//	    return nil
//	}, func(limit, offset int) ([]relayhub.DeadLetterJob, error) {
//	    return client.DLQ.List(ctx, "", limit, offset)
//	})
func Paginate[T any](pageSize int, onItem func(T) error, fetchPage FetchPageFunc[T]) error {
	offset := 0
	for {
		page, err := fetchPage(pageSize, offset)
		if err != nil {
			return err
		}
		for _, item := range page {
			if err := onItem(item); err != nil {
				return err
			}
		}
		if len(page) < pageSize {
			return nil
		}
		offset += pageSize
	}
}

// CollectAll gathers every page into a single slice. Convenient for small
// result sets; prefer Paginate for large ones so you don't hold everything in memory.
func CollectAll[T any](pageSize int, fetchPage FetchPageFunc[T]) ([]T, error) {
	var all []T
	err := Paginate(pageSize, func(item T) error {
		all = append(all, item)
		return nil
	}, fetchPage)
	return all, err
}
