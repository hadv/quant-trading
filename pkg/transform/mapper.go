package transform

// MapList iterates over a slice of type T1, applies mapFn to each element,
// and returns a new slice of type T2. If mapFn returns an error, the transformation halts.
func MapList[T1, T2 any](items []T1, mapFn func(T1) (T2, error)) ([]T2, error) {
	result := make([]T2, 0, len(items))
	for _, item := range items {
		r, err := mapFn(item)
		if err != nil {
			return nil, err
		}
		result = append(result, r)
	}
	return result, nil
}
