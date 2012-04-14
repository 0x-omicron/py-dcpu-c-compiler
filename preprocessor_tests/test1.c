#ifndef FUNC_FOO
#define FUNC_FOO
int foo(int a, int b) {
    return (a + b);
}
#endif

#ifndef FUNC_BAR
    #ifndef FUNC_FOO
    // neither foo nor bar defined

    #endif

    #ifdef FUNC_FOO 
    // bar not defined, foo defined

    #endif
#endif

#ifndef CONST_PI
#define CONST_PI (3.14159)
#endif

float area(float r) {
    return r * r * CONST_PI;
}
