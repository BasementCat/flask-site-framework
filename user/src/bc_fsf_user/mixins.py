def CompareProperty(prop: str):
    class ComparePropertyImpl:
        def __eq__(self, other):
            if not hasattr(other, prop):
                return False
            return getattr(self, prop) == getattr(other, prop)

        def __ne__(self, other):
            if not hasattr(other, prop):
                return True
            return getattr(self, prop) != getattr(other, prop)

        def __lt__(self, other):
            if not hasattr(other, prop):
                raise ValueError(f"Incompatible type for <{self.__class__.__name__}> <: {type(other)}")
            return getattr(self, prop) < getattr(other, prop)

        def __le__(self, other):
            if not hasattr(other, prop):
                raise ValueError(f"Incompatible type for <{self.__class__.__name__}> <=: {type(other)}")
            return getattr(self, prop) <= getattr(other, prop)

        def __gt__(self, other):
            if not hasattr(other, prop):
                raise ValueError(f"Incompatible type for <{self.__class__.__name__}> >: {type(other)}")
            return getattr(self, prop) > getattr(other, prop)

        def __ge__(self, other):
            if not hasattr(other, prop):
                raise ValueError(f"Incompatible type for <{self.__class__.__name__}> >=: {type(other)}")
            return getattr(self, prop) >= getattr(other, prop)

    return ComparePropertyImpl