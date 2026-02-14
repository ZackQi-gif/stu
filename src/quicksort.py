def quicksort(arr):
    """对列表进行快速排序，返回新的已排序列表。"""
    if len(arr) <= 1:
        return arr

    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]

    return quicksort(left) + middle + quicksort(right)


def quicksort_inplace(arr, low=0, high=None):
    """原地快速排序，直接修改原列表。"""
    if high is None:
        high = len(arr) - 1

    if low < high:
        pivot_index = _partition(arr, low, high)
        quicksort_inplace(arr, low, pivot_index - 1)
        quicksort_inplace(arr, pivot_index + 1, high)


def _partition(arr, low, high):
    """分区函数，返回基准元素的最终位置。"""
    pivot = arr[high]
    i = low - 1

    for j in range(low, high):
        if arr[j] <= pivot:
            i += 1
            arr[i], arr[j] = arr[j], arr[i]

    arr[i + 1], arr[high] = arr[high], arr[i + 1]
    return i + 1


if __name__ == "__main__":
    data = [38, 27, 43, 3, 9, 82, 10]
    print(f"原始数组: {data}")
    print(f"排序结果: {quicksort(data)}")

    data2 = [38, 27, 43, 3, 9, 82, 10]
    quicksort_inplace(data2)
    print(f"原地排序: {data2}")
