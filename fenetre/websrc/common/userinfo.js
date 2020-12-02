import React from 'react';

const UserInfoContext = React.createContext();

function UserInfoProvider(props) {
	return <UserInfoContext.Provider value={window.userinfo}>
		{props.children}
	</UserInfoContext.Provider>;
}

export { UserInfoProvider, UserInfoContext };
