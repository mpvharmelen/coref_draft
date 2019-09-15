from functools import partial


class SieveRunner:
    """
    Hopefully temporary wrapper class to run a sieve.
    """
    def __init__(self, entities):
        self.entities = entities

    def run(self, sieve, entity_filter, **kwargs):
        """
        Run a `sieve` with `entity`, `candidates` and `mark_disjoint` as first
        three arguments, followed by all keyword arguments passed to this
        function. A `sieve` must return the `candidate` with which `entity`
        should be merged, or `None`.
        """
        for entity in filter(entity_filter, self.entities):
            match = sieve(
                entity,
                self.entities.get_candidates(entity),
                partial(self.entities.mark_disjoint, entity),
                **kwargs
            )
            if match is not None:
                self.entities.merge(match, entity)
