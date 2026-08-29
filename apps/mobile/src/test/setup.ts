// React Native Testing Library 14 registers its Jest matchers automatically.

jest.mock("react-native-safe-area-context", () => {
  const React = require("react");
  const { View } = require("react-native");
  const safeAreaMock = require("react-native-safe-area-context/jest/mock").default;
  const SafeAreaView = React.forwardRef(
    (props: Record<string, unknown>, ref: unknown) => React.createElement(View, { ...props, ref }),
  );
  return { ...safeAreaMock, SafeAreaView };
});

jest.mock("lucide-react-native", () => {
  const React = require("react");
  const { View } = require("react-native");
  const MockIcon = (props: Record<string, unknown>) => React.createElement(View, props);
  return new Proxy({}, { get: () => MockIcon });
});
