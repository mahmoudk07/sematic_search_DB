from __future__ import annotations


import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import euclidean_distances
import faiss 


BITS2DTYPE = {
    8: np.uint8,   ## nbits  we will use 16 or 32
    16:np.uint16,
    32:np.uint32,
}


class CustomIndexPQ:
    """Custom IndexPQ implementation.

    Parameters
    ----------
    d
        Dimensionality of the original vectors.

    m
        Number of segments.

    nbits
        Number of bits.

    estimator_kwargs
        Additional hyperparameters passed onto the sklearn KMeans
        class.

    """

    def __init__(
        self,
        d: int,
        m: int,
        nbits: int,
        **estimator_kwargs: str | int,
    ) -> None:
        if d % m != 0:
            raise ValueError("d needs to be a multiple of m")

        if nbits not in BITS2DTYPE:
            raise ValueError(f"Unsupported number of bits {nbits}")

        self.m = m       
        self.k = 2**nbits
        self.d = d
        self.ds = d // m  ## 3dd variables fe subvector 

        self.estimators = [
            KMeans(n_clusters=self.k, **estimator_kwargs) for _ in range(m) ## Kmeans lkol subvector
        ]

        self.is_trained = False

        self.dtype = BITS2DTYPE[nbits]
        self.dtype_orig = np.float32
        ## codes table needed to be stored on disk
        self.codes: np.ndarray | None = None

    def train(self, X: np.ndarray) -> None:
        """Train all KMeans estimators.
         neede to be changed with large numbers
        Parameters
        ----------
        X
            Array of shape `(n, d)` and dtype `float32`.

        """
        if self.is_trained:
            raise ValueError("Training multiple times is not allowed")

        for i in range(self.m):
            estimator = self.estimators[i]  ## bngeeb kol kmean
            X_i = X[:, i * self.ds : (i + 1) * self.ds]

            estimator.fit(X_i)

        self.is_trained = True


    def encode(self, X: np.ndarray) -> np.ndarray:
        """Encode original features into codes.
           run after train to get code table 
        Parameters
        ----------
        X
            Array of shape `(n_queries, d)` of dtype `np.float32`.

        Returns
        -------
        result
            Array of shape `(n_queries, m)` of dtype `np.uint8` or np.uint16 or np.uint32 .
        """
        n = len(X)
        result = np.empty((n, self.m), dtype=self.dtype)

        for i in range(self.m):
            estimator = self.estimators[i]
            X_i = X[:, i * self.ds : (i + 1) * self.ds]
            result[:, i] = estimator.predict(X_i)

        return result     ### codes table

    def add(self, X: np.ndarray) -> None:
        """Add vectors to the database (their encoded versions).

        Parameters
        ----------
        X
            Array of shape `(n_codes, d)` of dtype `np.float32`.
        """
        if not self.is_trained:
            raise ValueError("The quantizer needs to be trained first.")
        self.codes = self.encode(X)    ### save table 

    def compute_asymmetric_distances(self, X: np.ndarray) -> np.ndarray:
        """Compute asymmetric distances to all database codes.

        Parameters
        ----------
        X
            Array of shape `(n_queries, d)` of dtype `np.float32`.

        Returns
        -------
        distances
            Array of shape `(n_queries, n_codes)` of dtype `np.float32`.

        """
        if not self.is_trained:
            raise ValueError("The quantizer needs to be trained first.")

        if self.codes is None:
            raise ValueError("No codes detected. You need to run `add` first")

        n_queries = len(X)
        n_codes = len(self.codes)

        distance_table = np.empty(
            (n_queries, self.m, self.k), dtype=self.dtype_orig
        )  # (n_queries, m, k)

        for i in range(self.m):
            X_i = X[:, i * self.ds : (i + 1) * self.ds]  # (n_queries, ds)
            centers = self.estimators[i].cluster_centers_  # (k, ds)
            distance_table[:, i, :] = euclidean_distances(
                X_i, centers, squared=True
            )

        distances = np.zeros((n_queries, n_codes), dtype=self.dtype_orig)

        for i in range(self.m):
            distances += distance_table[:, i, self.codes[:, i]]

        return distances

    def search(self, X: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
        """Find k closest database codes to given queries.

        Parameters
        ----------
        X
            Array of shape `(n_queries, d)` of dtype `np.float32`.

        k
            The number of closest codes to look for.

        Returns
        -------
        distances
            Array of shape `(n_queries, k)`.

        indices
            Array of shape `(n_queries, k)`.
        """
        n_queries = len(X)
        distances_all = self.compute_asymmetric_distances(X)

        indices = np.argsort(distances_all, axis=1)[:, :k]

        distances = np.empty((n_queries, k), dtype=np.float32)
        for i in range(n_queries):
            distances[i] = distances_all[i][indices[i]]

        return distances, indices
    
    
    
query_vector =  np.random.rand(1, 70).astype(np.float32)
data = np.load('vectorsdata.npy')
index = faiss.IndexFlatIP(data.shape[1])
index.add(data)
distances, indices = index.search(query_vector, 20)

indexx= CustomIndexPQ(d=70, m=10, nbits=16,init='random',max_iter=20)

index.train(data)
index.add(data)
dist,idices= index.search(query_vector , 20)


"""vectors = np.random.rand(20000000, 70).astype(np.float32)"""
"""
vectors = np.random.rand(200000, 70).astype(np.float32)

# Save to a .npy file
np.save('vectorsdata.npy', vectors)

"""



