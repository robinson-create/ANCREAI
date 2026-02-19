import {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
} from "react"

interface SearchViewContextType {
  /** True when search page is in "home" mode (no active conversation) */
  isSearchHome: boolean
  setSearchHome: (value: boolean) => void
}

const SearchViewContext = createContext<SearchViewContextType | null>(null)

export function SearchViewProvider({ children }: { children: ReactNode }) {
  const [isSearchHome, setSearchHomeState] = useState(true)
  const setSearchHome = useCallback((value: boolean) => {
    setSearchHomeState(value)
  }, [])

  return (
    <SearchViewContext.Provider value={{ isSearchHome, setSearchHome }}>
      {children}
    </SearchViewContext.Provider>
  )
}

export function useSearchView() {
  const ctx = useContext(SearchViewContext)
  return ctx
}
