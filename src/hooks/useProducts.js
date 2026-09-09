import { useCallback, useEffect, useRef, useState } from 'react';
import * as api from '../services/api.js';

/**
 * უნივერსალური async-fetch hook loading → success → error მდგომარეობებით.
 * გამოიყენება ყველა სიისა და დეტალური გვერდისთვის.
 *
 * @param {() => Promise<any>} fetcher
 * @param {any[]} deps
 * @param {{ skip?: boolean, initialData?: any }} [options]
 */
export function useAsync(fetcher, deps = [], options = {}) {
  const { skip = false, initialData = null } = options;
  const [data, setData] = useState(initialData);
  const [loading, setLoading] = useState(!skip);
  const [error, setError] = useState(null);
  const [reloadToken, setReloadToken] = useState(0);

  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  useEffect(() => {
    if (skip) {
      setLoading(false);
      return undefined;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    fetcherRef
      .current()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, skip, reloadToken]);

  const reload = useCallback(() => setReloadToken((n) => n + 1), []);

  return { data, loading, error, reload, setData };
}

/**
 * პროდუქტების სია — ფილტრებით, სორტით და პაგინაციით.
 * @param {{ category?:string, filters?:object, sort?:string, page?:number, limit?:number, q?:string }} params
 */
export function useProducts(params, options = {}) {
  const serialized = JSON.stringify(params ?? {});
  const fetcher = useCallback(() => api.getProducts(JSON.parse(serialized)), [serialized]);
  return useAsync(fetcher, [serialized], options);
}

/** ერთი პროდუქტი slug-ით. */
export function useProduct(slug) {
  const fetcher = useCallback(() => api.getProductBySlug(slug), [slug]);
  return useAsync(fetcher, [slug], { skip: !slug });
}

/** მსგავსი პროდუქტები. */
export function useRelatedProducts(productId, limit = 4) {
  const fetcher = useCallback(() => api.getRelatedProducts(productId, limit), [productId, limit]);
  return useAsync(fetcher, [productId, limit], { skip: !productId, initialData: [] });
}

/**
 * კატეგორიების სია.
 * შედეგი იქეშება სესიის განმავლობაში — Header, Footer და Category გვერდი
 * ერთსა და იმავე promise-ს იზიარებენ.
 */
let categoriesPromise = null;

export function useCategories() {
  const fetcher = useCallback(() => {
    if (!categoriesPromise) categoriesPromise = api.getCategories();
    return categoriesPromise;
  }, []);
  return useAsync(fetcher, [], { initialData: [] });
}

export default useProducts;
