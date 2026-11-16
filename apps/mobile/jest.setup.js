/* eslint-env jest */
jest.mock('@react-native-async-storage/async-storage', () =>
  require('@react-native-async-storage/async-storage/jest/async-storage-mock'),
);

// An in-memory keystore. Tests read it through the same expo-secure-store functions the app uses.
jest.mock('expo-secure-store', () => {
  const items = new Map();
  return {
    getItemAsync: jest.fn(async (key) => (items.has(key) ? items.get(key) : null)),
    setItemAsync: jest.fn(async (key, value) => {
      items.set(key, value);
    }),
    deleteItemAsync: jest.fn(async (key) => {
      items.delete(key);
    }),
  };
});

jest.mock('expo-router', () => {
  const router = { push: jest.fn(), navigate: jest.fn(), replace: jest.fn(), back: jest.fn(), canGoBack: jest.fn(() => true) };
  return {
    router,
    useRouter: () => router,
    useLocalSearchParams: () => ({}),
    // Runs like an effect: once when the screen mounts, standing in for the first focus.
    useFocusEffect: (effect) => require('react').useEffect(effect, [effect]),
    Link: ({ children }) => children,
    Stack: Object.assign(() => null, { Screen: () => null }),
  };
});

jest.mock('react-native-screens/experimental', () => ({ SafeAreaView: require('react-native').View }));
